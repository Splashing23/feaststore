"""Integration tests for the Postgres-backed registry and offline point-in-time join.

Marked `integration`; run with `pytest -m integration`. They spin up a throwaway
Postgres via testcontainers, so Docker must be available. CI runs these against a
service container instead (see .github/workflows/ci.yml).
"""

from __future__ import annotations

import os
from datetime import timedelta

import pandas as pd
import pytest

from feaststore.config import Settings
from feaststore.definitions import Entity, Feature, FeatureView, ValueType
from feaststore.offline_store import OfflineStore
from feaststore.registry import Registry

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_dsn():
    # Prefer an externally-provided DSN (CI service container); else spin one up.
    if dsn := os.getenv("FEASTSTORE_OFFLINE_DSN"):
        yield dsn
        return
    testcontainers = pytest.importorskip("testcontainers.postgres")
    with testcontainers.PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url().replace("psycopg2", "psycopg")


@pytest.fixture
def settings(pg_dsn):
    return Settings(offline_dsn=pg_dsn, project="itest")


def test_registry_apply_and_list(settings, driver_view):
    reg = Registry(settings)
    reg.init_schema()
    reg.apply(driver_view)

    fetched = reg.get_feature_view("driver_hourly_stats")
    assert fetched == driver_view
    assert any(v.name == "driver_hourly_stats" for v in reg.list_feature_views())


def test_registry_upsert_is_idempotent(settings, driver_view):
    reg = Registry(settings)
    reg.init_schema()
    reg.apply(driver_view)
    reg.apply(driver_view)
    matches = [v for v in reg.list_feature_views() if v.name == driver_view.name]
    assert len(matches) == 1


def test_point_in_time_join_no_leakage(settings):
    """Feature values from *after* the label timestamp must not leak in."""
    view = FeatureView(
        name="driver_hourly_stats",
        entities=[Entity("driver", "driver_id")],
        features=[Feature("conv_rate", ValueType.FLOAT)],
        source_table="pit_source",
        ttl=timedelta(days=30),
    )
    offline = OfflineStore(settings)
    source = pd.DataFrame(
        {
            "driver_id": [1, 1, 1],
            "conv_rate": [0.1, 0.2, 0.3],
            "event_timestamp": pd.to_datetime(["2025-01-01", "2025-01-10", "2025-01-20"]),
        }
    )
    with offline._engine.begin() as conn:
        source.to_sql("pit_source", conn, index=False, if_exists="replace")

    entity_df = pd.DataFrame(
        {
            "driver_id": [1],
            "event_timestamp": pd.to_datetime(["2025-01-12"]),
        }
    )
    result = offline.get_historical_features(entity_df, [view])
    # as of 2025-01-12 the newest row is the 2025-01-10 value (0.2), not 0.3
    assert result["conv_rate"].tolist() == [0.2]
