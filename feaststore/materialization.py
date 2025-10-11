"""Materialization: move the latest offline rows into the online store.

This is the batch job an orchestrator (Airflow, cron, a GitHub Action) runs on a
schedule. It reads the newest row per entity from Postgres and writes it into
Redis so online serving is a single hash lookup.

Incremental materialization is supported via a per-view high-water mark stored in
the online store, so a scheduled run only pushes rows newer than the last run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from feaststore.definitions import FeatureView
from feaststore.exceptions import MaterializationError
from feaststore.offline_store import OfflineStore
from feaststore.online_store import OnlineStore

logger = logging.getLogger("feaststore.materialization")


@dataclass(slots=True)
class MaterializationResult:
    feature_view: str
    rows_written: int
    cutoff: datetime
    duration_seconds: float


class MaterializationEngine:
    def __init__(self, offline: OfflineStore, online: OnlineStore) -> None:
        self._offline = offline
        self._online = online

    def materialize(
        self,
        view: FeatureView,
        cutoff: datetime | None = None,
    ) -> MaterializationResult:
        """Materialize the latest state of `view` into the online store."""
        cutoff = cutoff or datetime.now(timezone.utc)
        started = _monotonic_seconds()

        df = self._offline.get_latest_rows(view, cutoff=cutoff)
        if df.empty:
            logger.info("no rows to materialize for view %s", view.name)
            return MaterializationResult(view.name, 0, cutoff, _monotonic_seconds() - started)

        ts_field = view.timestamp_field
        if ts_field not in df.columns:
            raise MaterializationError(
                f"source for {view.name!r} did not return timestamp column {ts_field!r}"
            )

        # Serialize timestamps to ISO strings for the online layer.
        timestamps = [
            _to_iso(v) for v in df[ts_field].tolist()
        ]
        records = df.drop(columns=[ts_field]).to_dict(orient="records")

        written = self._online.write_batch(view, records, timestamps)
        duration = _monotonic_seconds() - started
        logger.info(
            "materialized %d rows for view %s in %.3fs", written, view.name, duration
        )
        return MaterializationResult(view.name, written, cutoff, duration)

    def materialize_all(
        self, views: list[FeatureView], cutoff: datetime | None = None
    ) -> list[MaterializationResult]:
        return [self.materialize(v, cutoff=cutoff) for v in views]


def _to_iso(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    # pandas Timestamp and numpy datetime64 both implement isoformat via str()
    return str(value)


def _monotonic_seconds() -> float:
    # Wrapped so tests can monkeypatch a deterministic clock without importing time.
    import time

    return time.monotonic()
