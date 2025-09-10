from __future__ import annotations

from datetime import timedelta

import pytest

from feaststore.definitions import Entity, Feature, FeatureView, ValueType
from feaststore.exceptions import RegistrationError


def test_entity_defaults_join_key_to_name():
    e = Entity(name="user")
    assert e.join_key == "user"


def test_entity_explicit_join_key():
    e = Entity(name="user", join_key="user_id")
    assert e.join_key == "user_id"


@pytest.mark.parametrize("bad", ["User", "1user", "user-id", "", "a" * 64])
def test_invalid_entity_names_rejected(bad):
    with pytest.raises(RegistrationError):
        Entity(name=bad)


def test_feature_requires_valuetype():
    with pytest.raises(RegistrationError):
        Feature(name="x", dtype="float")  # type: ignore[arg-type]


def test_feature_view_requires_entities_and_features():
    with pytest.raises(RegistrationError):
        FeatureView(name="v", entities=[], features=[Feature("x", ValueType.FLOAT)], source_table="t")
    with pytest.raises(RegistrationError):
        FeatureView(name="v", entities=[Entity("e")], features=[], source_table="t")


def test_feature_view_rejects_duplicate_features():
    with pytest.raises(RegistrationError, match="duplicate"):
        FeatureView(
            name="v",
            entities=[Entity("e")],
            features=[Feature("x", ValueType.FLOAT), Feature("x", ValueType.INT64)],
            source_table="t",
        )


def test_feature_view_join_keys(driver_view):
    assert driver_view.join_keys == ["driver_id"]
    assert driver_view.feature_names() == ["conv_rate", "acc_rate", "avg_daily_trips"]


def test_roundtrip_serialization(driver_view):
    restored = FeatureView.from_dict(driver_view.to_dict())
    assert restored == driver_view


def test_roundtrip_preserves_none_ttl():
    v = FeatureView(
        name="static_dims",
        entities=[Entity("user", "user_id")],
        features=[Feature("signup_country", ValueType.STRING)],
        source_table="user_dims",
        ttl=None,
    )
    restored = FeatureView.from_dict(v.to_dict())
    assert restored.ttl is None


def test_composite_ttl_roundtrip():
    v = FeatureView(
        name="v",
        entities=[Entity("a"), Entity("b")],
        features=[Feature("f", ValueType.FLOAT)],
        source_table="t",
        ttl=timedelta(hours=6),
    )
    assert FeatureView.from_dict(v.to_dict()).ttl == timedelta(hours=6)
    assert v.join_keys == ["a", "b"]


def test_get_feature(driver_view):
    assert driver_view.get_feature("conv_rate").dtype == ValueType.FLOAT
    with pytest.raises(KeyError):
        driver_view.get_feature("missing")
