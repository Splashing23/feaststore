"""Offline store backed by Postgres.

Two responsibilities:

1. ``get_latest_rows`` -- read the freshest feature row per entity up to a cutoff
   timestamp. The materialization engine uses this to populate the online store.

2. ``get_historical_features`` -- the point-in-time correct join. Given an entity
   dataframe with an ``event_timestamp`` per row (the label timestamp), attach for
   each feature view the feature values that were known *at or before* that
   timestamp and no older than the view's ttl. This is what prevents label
   leakage in training sets.

The point-in-time join is expressed as a LATERAL subquery so Postgres can use the
``(join_key, event_timestamp DESC)`` index and evaluate one correlated lookup per
entity row rather than materializing a full cross join.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from feaststore.config import Settings, get_settings
from feaststore.definitions import FeatureView


class OfflineStore:
    def __init__(self, settings: Settings | None = None, engine: Engine | None = None) -> None:
        self._settings = settings or get_settings()
        self._engine = engine or create_engine(
            self._settings.offline_dsn, future=True, pool_pre_ping=True
        )

    def get_latest_rows(self, view: FeatureView, cutoff: datetime | None = None) -> pd.DataFrame:
        """Latest row per entity as of `cutoff` (defaults to now).

        Uses ``DISTINCT ON`` -- a Postgres idiom that returns the first row per
        partition given an ordering, which is exactly "newest row per entity".
        """
        cols = ", ".join([*view.join_keys, *view.feature_names(), view.timestamp_field])
        join_keys = ", ".join(view.join_keys)
        params: dict[str, Any] = {}
        where = ""
        if cutoff is not None:
            where = f"WHERE {view.timestamp_field} <= :cutoff"
            params["cutoff"] = cutoff

        sql = text(
            f"""
            SELECT DISTINCT ON ({join_keys}) {cols}
            FROM {view.source_table}
            {where}
            ORDER BY {join_keys}, {view.timestamp_field} DESC
            """
        )
        with self._engine.connect() as conn:
            return pd.read_sql(sql, conn, params=params)

    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        views: list[FeatureView],
        features: dict[str, list[str]] | None = None,
        timestamp_col: str = "event_timestamp",
    ) -> pd.DataFrame:
        """Point-in-time correct join of `views` onto `entity_df`.

        `entity_df` must contain every join key referenced by `views` plus a
        `timestamp_col` column. `features` optionally restricts which features to
        pull per view name; by default all features in the view are returned.
        """
        if timestamp_col not in entity_df.columns:
            raise ValueError(f"entity_df is missing the timestamp column {timestamp_col!r}")

        result = entity_df.reset_index(drop=True).copy()
        result["_row_id"] = range(len(result))

        with self._engine.connect() as conn:
            for view in views:
                wanted = (features or {}).get(view.name, view.feature_names())
                result = self._join_one_view(conn, result, view, wanted, timestamp_col)

        return result.drop(columns=["_row_id"])

    def _join_one_view(
        self,
        conn: Any,
        entity_df: pd.DataFrame,
        view: FeatureView,
        wanted_features: list[str],
        timestamp_col: str,
    ) -> pd.DataFrame:
        # Push the small entity dataframe into a temp table so the LATERAL join
        # runs entirely server-side instead of issuing one query per row.
        entity_slice = entity_df[["_row_id", *view.join_keys, timestamp_col]].copy()
        tmp = f"_entities_{view.name}"
        entity_slice.to_sql(tmp, conn, index=False, if_exists="replace")

        select_feats = ", ".join(f"src.{f} AS {f}" for f in wanted_features)
        join_cond = " AND ".join(f"src.{jk} = e.{jk}" for jk in view.join_keys)
        ttl_clause = ""
        if view.ttl is not None:
            ttl_clause = (
                f"AND src.{view.timestamp_field} "
                f">= e.{timestamp_col} - INTERVAL '{int(view.ttl.total_seconds())} seconds'"
            )

        sql = text(
            f"""
            SELECT e._row_id, {select_feats}
            FROM {tmp} e
            LEFT JOIN LATERAL (
                SELECT {", ".join(wanted_features)}
                FROM {view.source_table} src
                WHERE {join_cond}
                  AND src.{view.timestamp_field} <= e.{timestamp_col}
                  {ttl_clause}
                ORDER BY src.{view.timestamp_field} DESC
                LIMIT 1
            ) src ON true
            """
        )
        joined = pd.read_sql(sql, conn)
        conn.exec_driver_sql(f"DROP TABLE IF EXISTS {tmp}")

        # Prefix collisions are possible if two views share a feature name; the
        # registry forbids that within a view but not across views, so namespace
        # ambiguous columns with the view name.
        return entity_df.merge(joined, on="_row_id", how="left")
