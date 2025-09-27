from __future__ import annotations

from datetime import timedelta

import fakeredis
import pytest

from feaststore.definitions import Entity, Feature, FeatureView, ValueType
from feaststore.online_store import OnlineStore


@pytest.fixture
def store(settings):
    client = fakeredis.FakeRedis(decode_responses=True)
    return OnlineStore(settings=settings, client=client)


def test_write_and_read_roundtrip(store, driver_view):
    rows = [
        {"driver_id": 1001, "conv_rate": 0.5, "acc_rate": 0.9, "avg_daily_trips": 10},
        {"driver_id": 1002, "conv_rate": 0.7, "acc_rate": 0.8, "avg_daily_trips": 20},
    ]
    ts = ["2025-01-01T00:00:00", "2025-01-01T00:00:00"]
    assert store.write_batch(driver_view, rows, ts) == 2

    out = store.read(driver_view, [{"driver_id": 1001}, {"driver_id": 1002}])
    assert out[0]["conv_rate"] == 0.5
    assert out[1]["avg_daily_trips"] == 20
    assert out[0]["driver_id"] == 1001


def test_missing_entity_returns_none(store, driver_view):
    out = store.read(driver_view, [{"driver_id": 9999}])
    assert out[0]["conv_rate"] is None
    assert out[0]["driver_id"] == 9999


def test_partial_feature_selection(store, driver_view):
    store.write_batch(
        driver_view,
        [{"driver_id": 1, "conv_rate": 0.1, "acc_rate": 0.2, "avg_daily_trips": 3}],
        ["2025-01-01T00:00:00"],
    )
    out = store.read(driver_view, [{"driver_id": 1}], features=["conv_rate"])
    assert out[0]["conv_rate"] == 0.1
    assert "acc_rate" not in out[0]


def test_composite_key():
    view = FeatureView(
        name="pair_stats",
        entities=[Entity("user", "user_id"), Entity("merchant", "merchant_id")],
        features=[Feature("txn_count", ValueType.INT64)],
        source_table="t",
    )
    client = fakeredis.FakeRedis(decode_responses=True)
    store = OnlineStore(client=client)
    store.write_batch(
        view,
        [{"user_id": 1, "merchant_id": 42, "txn_count": 5}],
        ["2025-01-01T00:00:00"],
    )
    out = store.read(view, [{"user_id": 1, "merchant_id": 42}])
    assert out[0]["txn_count"] == 5
    # wrong pairing must miss
    assert store.read(view, [{"user_id": 1, "merchant_id": 99}])[0]["txn_count"] is None


def test_ttl_applied(store, driver_view):
    store.write_batch(
        driver_view,
        [{"driver_id": 1, "conv_rate": 0.1, "acc_rate": 0.2, "avg_daily_trips": 3}],
        ["2025-01-01T00:00:00"],
    )
    key = store._key(driver_view, "1")
    ttl = store._client.ttl(key)
    assert 0 < ttl <= int(timedelta(days=3).total_seconds())


def test_length_mismatch_raises(store, driver_view):
    with pytest.raises(ValueError):
        store.write_batch(driver_view, [{"driver_id": 1}], [])
