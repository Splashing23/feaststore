"""Online store backed by Redis.

Layout: one Redis hash per (feature view, entity key). The hash field is the
feature name; the value is the msgpack-free JSON-encoded feature value plus a
sentinel event timestamp field. TTL is applied at the key level from the feature
view's `ttl`, so stale entities fall out of the cache automatically.

Key format:  ``{namespace}:{feature_view}:{join_key_value}``
  e.g.       ``fs:default:driver_hourly_stats:1005``

For composite entity keys the join-key values are joined with ``|`` in the order
the feature view declares its entities.
"""

from __future__ import annotations

import json
from typing import Any

import redis

from feaststore.config import Settings, get_settings
from feaststore.definitions import FeatureView

# Reserved hash field holding the event timestamp of the materialized row.
_TS_FIELD = "_event_ts"


class OnlineStore:
    def __init__(self, settings: Settings | None = None, client: redis.Redis | None = None) -> None:
        self._settings = settings or get_settings()
        self._client = client or redis.Redis.from_url(
            self._settings.online_redis_url, decode_responses=True
        )

    def _key(self, view: FeatureView, entity_key: str) -> str:
        return f"{self._settings.redis_namespace}:{view.name}:{entity_key}"

    @staticmethod
    def _compose_entity_key(view: FeatureView, entity_row: dict[str, Any]) -> str:
        parts = []
        for jk in view.join_keys:
            if jk not in entity_row:
                raise KeyError(f"entity row missing join key {jk!r} for view {view.name!r}")
            parts.append(str(entity_row[jk]))
        return "|".join(parts)

    def write_batch(
        self,
        view: FeatureView,
        rows: list[dict[str, Any]],
        event_timestamps: list[str],
    ) -> int:
        """Write a batch of feature rows for a view. Returns the number written.

        `rows` contains join keys + feature values; `event_timestamps` are ISO
        strings aligned by index. Writes are pipelined for throughput.
        """
        if len(rows) != len(event_timestamps):
            raise ValueError("rows and event_timestamps must be the same length")

        ttl_seconds = int(view.ttl.total_seconds()) if view.ttl else None
        feature_names = view.feature_names()

        pipe = self._client.pipeline(transaction=False)
        for row, ts in zip(rows, event_timestamps, strict=True):
            entity_key = self._compose_entity_key(view, row)
            key = self._key(view, entity_key)
            mapping = {name: json.dumps(row.get(name)) for name in feature_names}
            mapping[_TS_FIELD] = ts
            # redis-py types `mapping` with an invariant Mapping key union, so a
            # plain dict[str, str] is flagged despite being valid at runtime.
            pipe.hset(key, mapping=mapping)  # type: ignore[arg-type]
            if ttl_seconds is not None:
                pipe.expire(key, ttl_seconds)
        pipe.execute()
        return len(rows)

    def read(
        self,
        view: FeatureView,
        entity_rows: list[dict[str, Any]],
        features: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Read feature values for a set of entity rows.

        Missing entities and missing features come back as ``None`` so the caller
        always gets a dense, rectangular result aligned with `entity_rows`.
        """
        requested = features or view.feature_names()
        pipe = self._client.pipeline(transaction=False)
        for row in entity_rows:
            entity_key = self._compose_entity_key(view, row)
            pipe.hmget(self._key(view, entity_key), requested)
        raw_results = pipe.execute()

        out: list[dict[str, Any]] = []
        for row, raw in zip(entity_rows, raw_results, strict=True):
            record: dict[str, Any] = {jk: row[jk] for jk in view.join_keys}
            for name, value in zip(requested, raw, strict=True):
                record[name] = json.loads(value) if value is not None else None
            out.append(record)
        return out

    def ping(self) -> bool:
        return bool(self._client.ping())

    def close(self) -> None:
        self._client.close()
