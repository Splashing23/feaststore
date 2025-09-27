from __future__ import annotations

from datetime import timedelta

import pytest

from feaststore.config import Settings
from feaststore.definitions import Entity, Feature, FeatureView, ValueType


@pytest.fixture
def driver_view() -> FeatureView:
    driver = Entity(name="driver", join_key="driver_id", description="A rideshare driver")
    return FeatureView(
        name="driver_hourly_stats",
        entities=[driver],
        features=[
            Feature("conv_rate", ValueType.FLOAT),
            Feature("acc_rate", ValueType.FLOAT),
            Feature("avg_daily_trips", ValueType.INT64),
        ],
        source_table="driver_hourly_stats_source",
        ttl=timedelta(days=3),
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        online_redis_url="redis://localhost:6379/15",
        project="test",
    )
