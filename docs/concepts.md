# Concepts

## Entity

A domain object features hang off of — a card, a user, a merchant. Each entity has
a **join key**: the column used to join feature tables offline and the lookup key
online. It defaults to the entity name but is usually set explicitly
(`Entity("card", join_key="card_id")`).

## Feature

A single named, typed value (`Feature("txn_count_1h", ValueType.INT64)`). Types are
deliberately coarse — see the note on `ValueType` below.

## Feature view

A group of features computed from one source table, keyed by one or more entities.
The view carries:

- `source_table` — the offline relation the materialization engine reads.
- `timestamp_field` — the event-time column (`event_timestamp` by default).
- `ttl` — how long a materialized value stays fresh online, and the maximum
  look-back for point-in-time joins offline.

A feature view is the unit of materialization and the namespace for feature
references (`card_velocity:txn_count_1h`).

## Online vs offline

The same feature exists in two stores with different access patterns:

| | Offline (Postgres) | Online (Redis) |
|---|---|---|
| Purpose | training sets, backfills | real-time serving |
| Access | point-in-time join over history | point lookup, latest value |
| Latency | seconds–minutes | sub-millisecond |
| Written by | your ETL | the materialization engine |

## Point-in-time correctness

The cardinal rule of a training set: **for a label observed at time _t_, you may
only use feature values known at or before _t_.** Using a value from _t+1_ leaks
the future and inflates offline metrics that then collapse in production.

`get_historical_features` enforces this with a LATERAL join that, per entity row,
picks the newest source row with `event_timestamp <= label_timestamp` and no older
than the view's `ttl`. See [architecture.md](architecture.md) for the query shape.

## A note on `ValueType`

The type set is intentionally small (int/float/string/bool/bytes/timestamp).
Embeddings and lists are out of scope for the online path today; the roadmap item
is typed arrays with a length-prefixed binary encoding rather than JSON, to keep
the hot read path allocation-light.
