from __future__ import annotations

import pytest

from feaststore.store import _group_feature_refs


def test_group_feature_refs():
    grouped = _group_feature_refs(
        ["driver_stats:conv_rate", "driver_stats:acc_rate", "trip_stats:count"]
    )
    assert grouped == {
        "driver_stats": ["conv_rate", "acc_rate"],
        "trip_stats": ["count"],
    }


def test_group_feature_refs_rejects_malformed():
    with pytest.raises(ValueError, match="view:feature"):
        _group_feature_refs(["conv_rate"])


def test_group_preserves_feature_with_colon_in_name():
    # only the first colon splits view from feature
    grouped = _group_feature_refs(["view:a:b"])
    assert grouped == {"view": ["a:b"]}
