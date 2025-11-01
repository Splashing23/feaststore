"""Serving API tests.

These exercise the HTTP layer against a stubbed FeatureStore so they run without
Postgres or Redis. We override the `get_store` dependency with a fake that returns
canned online features.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from feaststore.serving import api
from feaststore.serving.api import app, get_store


class FakeOnline:
    def ping(self) -> bool:
        return True


class FakeStore:
    def __init__(self) -> None:
        self.online = FakeOnline()

    def get_online_features(
        self, features: list[str], entity_rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        out = []
        for row in entity_rows:
            rec = dict(row)
            for f in features:
                rec[f] = 0.42
            out.append(rec)
        return out

    def list_feature_views(self):
        return []


def _client() -> TestClient:
    app.dependency_overrides[get_store] = lambda: FakeStore()
    return TestClient(app)


def test_health_ok():
    with _client() as c:
        resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_get_online_features():
    with _client() as c:
        resp = c.post(
            "/get-online-features",
            json={
                "features": ["driver_hourly_stats:conv_rate"],
                "entities": [{"driver_id": 1001}, {"driver_id": 1002}],
            },
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["metadata"]["n_entities"] == 2
    assert body["results"][0]["driver_hourly_stats:conv_rate"] == 0.42


def test_malformed_feature_ref_rejected():
    with _client() as c:
        resp = c.post(
            "/get-online-features",
            json={"features": ["no_colon"], "entities": [{"driver_id": 1}]},
        )
    assert resp.status_code == 422


def test_metrics_endpoint_records_requests():
    with _client() as c:
        c.post(
            "/get-online-features",
            json={
                "features": ["v:f"],
                "entities": [{"driver_id": 1}],
            },
        )
        resp = c.get("/metrics")
    assert resp.status_code == 200
    assert "feaststore_requests_total" in resp.text


def teardown_module(_module):
    app.dependency_overrides.clear()
    _ = api  # keep import referenced
