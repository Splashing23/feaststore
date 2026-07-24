"""`FeatureStore` -- the top-level facade that ties the pieces together.

This is the object most users touch. It wraps the registry, offline store, online
store, and materialization engine behind the handful of verbs people actually
reach for: apply definitions, materialize, fetch online features for serving, and
build a historical training set.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from feaststore.config import Settings, get_settings
from feaststore.definitions import FeatureView
from feaststore.materialization import MaterializationEngine, MaterializationResult
from feaststore.offline_store import OfflineStore
from feaststore.online_store import OnlineStore
from feaststore.registry import Registry


class FeatureStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self.registry = Registry(self._settings)
        self.offline = OfflineStore(self._settings)
        self.online = OnlineStore(self._settings)
        self._engine = MaterializationEngine(self.offline, self.online)

    # --- definitions ---------------------------------------------------------

    def apply(self, views: FeatureView | list[FeatureView]) -> None:
        self.registry.init_schema()
        if isinstance(views, FeatureView):
            views = [views]
        self.registry.apply_all(views)

    def list_feature_views(self) -> list[FeatureView]:
        return self.registry.list_feature_views()

    # --- materialization -----------------------------------------------------

    def materialize(
        self, view_names: list[str] | None = None, cutoff: datetime | None = None
    ) -> list[MaterializationResult]:
        views = (
            [self.registry.get_feature_view(n) for n in view_names]
            if view_names
            else self.registry.list_feature_views()
        )
        return self._engine.materialize_all(views, cutoff=cutoff)

    # --- serving -------------------------------------------------------------

    def get_online_features(
        self,
        features: list[str],
        entity_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fetch online features.

        `features` are ``"view:feature"`` references. Entity rows supply the join
        keys. Results are merged per entity row across the referenced views.
        """
        by_view = _group_feature_refs(features)
        merged: list[dict[str, Any]] = [{} for _ in entity_rows]

        for view_name, feats in by_view.items():
            view = self.registry.get_feature_view(view_name)
            partial = self.online.read(view, entity_rows, features=feats)
            for i, rec in enumerate(partial):
                for f in feats:
                    merged[i][f"{view_name}:{f}"] = rec.get(f)
                for jk in view.join_keys:
                    merged[i].setdefault(jk, rec.get(jk))
        return merged

    def get_historical_features(
        self,
        entity_df: pd.DataFrame,
        features: list[str],
        timestamp_col: str = "event_timestamp",
    ) -> pd.DataFrame:
        by_view = _group_feature_refs(features)
        views = [self.registry.get_feature_view(v) for v in by_view]
        return self.offline.get_historical_features(
            entity_df, views, features=by_view, timestamp_col=timestamp_col
        )

    def close(self) -> None:
        self.online.close()


def _group_feature_refs(features: list[str]) -> dict[str, list[str]]:
    """Turn ``["view_a:x", "view_a:y", "view_b:z"]`` into a per-view mapping."""
    grouped: dict[str, list[str]] = {}
    for ref in features:
        if ":" not in ref:
            raise ValueError(f"feature reference {ref!r} must be of the form 'view:feature'")
        view_name, feature_name = ref.split(":", 1)
        grouped.setdefault(view_name, []).append(feature_name)
    return grouped
