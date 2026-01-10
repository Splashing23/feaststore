# feaststore

A lightweight **feature store** for serving ML features online and offline, with
point-in-time correctness built in. It solves the two problems every team hits
once a model leaves a notebook:

1. **Training/serving skew** — the code that builds features for training and the
   code that builds them at inference drift apart. feaststore computes a feature
   once, serves it both places.
2. **Label leakage** — naive joins pull feature values from *after* the label was
   observed, inflating offline metrics that collapse in production. feaststore's
   historical retrieval is point-in-time correct by construction.

It's deliberately small — Postgres for the offline store + registry, Redis for the
online store, FastAPI for serving. No Spark, no Kafka, no bespoke DSL. You define
features in plain Python and drive everything from a CLI.

> Not affiliated with Feast. This is a from-scratch project I built to understand
> feature-store internals — the point-in-time join and the online/offline split in
> particular — well enough to reason about the managed ones.

## Why it exists

I kept re-implementing the same "grab the latest feature per entity from Redis,
but reconstruct history correctly for training" logic across projects and wanted
one clean version of it with the point-in-time join done properly. The interesting
code is in [`offline_store.py`](feaststore/offline_store.py) (the LATERAL join) and
[`online_store.py`](feaststore/online_store.py) (the Redis layout + TTL). Design
notes live in [docs/architecture.md](docs/architecture.md).

## Features

- **Point-in-time correct** historical joins for leakage-free training sets
- **Online serving** at Redis-lookup latency, with per-view TTL
- **One definition, two stores** — features declared once in Python
- **Materialization** engine to push offline → online, idempotent and re-runnable
- **Composite entity keys** (e.g. features keyed on `(card, merchant)`)
- **FastAPI serving** with a Prometheus metrics endpoint
- **Typed CLI** (`feaststore apply | list | materialize | export`)

## Quickstart

```bash
make up                                       # postgres + redis
pip install -e ".[dev]"
make seed && make apply && make materialize   # load + register + push online
make serve                                    # FastAPI on :8000
```

```python
from feaststore.store import FeatureStore

store = FeatureStore()

# Online: latest values, for real-time inference
store.get_online_features(
    features=["card_velocity:txn_count_1h", "card_account:issuer_country"],
    entity_rows=[{"card_id": 1}, {"card_id": 2}],
)

# Offline: point-in-time correct history, for training
store.get_historical_features(entity_df=labels_df, features=[...])
```

Full walkthrough in [docs/quickstart.md](docs/quickstart.md).

## Defining features

```python
from datetime import timedelta
from feaststore import Entity, Feature, FeatureView, ValueType

card = Entity(name="card", join_key="card_id")

card_velocity = FeatureView(
    name="card_velocity",
    entities=[card],
    features=[
        Feature("txn_count_1h", ValueType.INT64),
        Feature("txn_amount_1h", ValueType.FLOAT),
    ],
    source_table="card_velocity_source",
    ttl=timedelta(hours=2),
)
```

A complete, realistic repo is in [`examples/fraud/`](examples/fraud/feature_repo.py).

## Architecture

```
feature repo (.py)  ─apply─▶  Registry (Postgres)
                                  │
        Offline store  ──materialize──▶  Online store (Redis)
        (Postgres, history)              │
              │ point-in-time join       │ point lookup
              ▼                           ▼
        training dataframe          Serving API (FastAPI)
```

See [docs/architecture.md](docs/architecture.md) for the store internals and the
point-in-time join query.

## Project layout

```
feaststore/
  definitions.py      # Entity / Feature / FeatureView (plain dataclasses)
  registry.py         # source of truth, Postgres-backed
  offline_store.py    # history + point-in-time LATERAL join
  online_store.py     # Redis hash-per-entity layout + TTL
  materialization.py  # offline -> online batch job
  store.py            # FeatureStore facade
  transforms.py       # windowed aggregations for building sources
  serving/            # FastAPI app + Prometheus metrics
  cli.py              # typer CLI
examples/fraud/       # end-to-end card-fraud feature repo + data generator
terraform/            # RDS + ElastiCache for a managed deploy
docs/                 # concepts, architecture, quickstart
```

## Development

```bash
make dev        # editable install with dev extras
make test       # unit tests (no external services; uses fakeredis)
make test-int   # integration tests (spins up Postgres via testcontainers)
make lint       # ruff
make typecheck  # mypy
```

CI runs lint + mypy, the unit suite on Python 3.10–3.12, and the integration suite
against Postgres/Redis service containers — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml).

## Roadmap

- [ ] Parquet/DuckDB offline backend for teams not on Postgres
- [ ] Typed array features (embeddings) with a binary online encoding
- [ ] Chunked temp-table load for very large entity dataframes
- [ ] On-demand (request-time) transformations
- [ ] gRPC serving alongside HTTP

## License

MIT — see [LICENSE](LICENSE).
