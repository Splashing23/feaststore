# Architecture

```
                    ┌────────────────────┐
   feature repo ───▶│      Registry      │  (Postgres: feature_views table)
   (.py defs)       └─────────┬──────────┘
                              │ definitions
             ┌────────────────┴─────────────────┐
             ▼                                   ▼
   ┌───────────────────┐  materialize   ┌──────────────────┐
   │  Offline store    │───────────────▶│  Online store    │
   │  (Postgres)       │  latest/entity │  (Redis hashes)   │
   │  history + PIT    │                └────────┬─────────┘
   └─────────┬─────────┘                         │ point lookup
             │ point-in-time join                ▼
             ▼                          ┌──────────────────┐
     training dataframe                 │  Serving API     │
     (get_historical_features)          │  (FastAPI)       │
                                        └──────────────────┘
```

## Components

- **Registry** (`registry.py`) — persists serialized feature-view specs as JSON
  rows keyed by `(project, name)`. Upsert semantics; the offline DB doubles as the
  registry DB to keep the moving parts down.

- **Offline store** (`offline_store.py`) — two queries: `get_latest_rows`
  (`DISTINCT ON` newest row per entity) feeds materialization;
  `get_historical_features` does the point-in-time join.

- **Online store** (`online_store.py`) — one Redis hash per
  `(feature_view, entity_key)`. Feature name → JSON value. Key-level TTL from the
  view's `ttl`. Reads and writes are pipelined.

- **Materialization** (`materialization.py`) — reads the newest offline rows up to
  a cutoff and pipelines them into Redis. Idempotent; safe to re-run.

- **Serving** (`serving/`) — FastAPI. Store built once at startup, shared across
  requests (Redis client and SQLAlchemy engine are both pooled).

## The point-in-time join

Expressed as a `LEFT JOIN LATERAL` so Postgres runs one correlated lookup per
entity row against the `(join_key, event_timestamp DESC)` index instead of a full
cross join:

```sql
SELECT e._row_id, src.conv_rate
FROM _entities e
LEFT JOIN LATERAL (
    SELECT conv_rate
    FROM driver_hourly_stats_source src
    WHERE src.driver_id = e.driver_id
      AND src.event_timestamp <= e.event_timestamp
      AND src.event_timestamp >= e.event_timestamp - INTERVAL '3 days'  -- ttl
    ORDER BY src.event_timestamp DESC
    LIMIT 1
) src ON true;
```

The entity dataframe is pushed into a temp table first so the whole join runs
server-side. For very large entity sets this is the piece to watch — the roadmap
note is to chunk the temp-table load and to support a Parquet/DuckDB offline
backend for teams not on Postgres.

## Consistency

Online and offline are eventually consistent: the online store lags the offline
store by at most the materialization interval. Training reads offline; serving
reads online. The ttl guards against serving a value the model would never have
seen offline (a stale value simply reads as `null`, which the model handles as a
missing feature).
