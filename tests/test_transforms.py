from __future__ import annotations

import pandas as pd
import pytest

from feaststore.transforms import fill_missing, windowed_aggregate


def _sample():
    return pd.DataFrame(
        {
            "driver_id": [1, 1, 1, 2, 2],
            "event_timestamp": pd.to_datetime(
                [
                    "2025-01-01",
                    "2025-01-02",
                    "2025-01-03",
                    "2025-01-01",
                    "2025-01-05",
                ]
            ),
            "trips": [1, 2, 3, 10, 20],
        }
    )


def test_windowed_sum_trailing_window():
    out = windowed_aggregate(
        _sample(),
        entity_col="driver_id",
        timestamp_col="event_timestamp",
        value_col="trips",
        window="2D",
        agg="sum",
    )
    got = out.sort_values(["driver_id", "event_timestamp"])["trips_sum_2D"].tolist()
    # driver 1: [1], [1+2], [2+3]; driver 2: [10], [20] (5 days apart -> window resets)
    assert got == [1.0, 3.0, 5.0, 10.0, 20.0]


def test_windowed_rejects_unknown_agg():
    with pytest.raises(ValueError, match="unsupported agg"):
        windowed_aggregate(
            _sample(),
            entity_col="driver_id",
            timestamp_col="event_timestamp",
            value_col="trips",
            window="2D",
            agg="median",
        )


def test_fill_missing():
    df = pd.DataFrame({"a": [1.0, None], "b": [None, "x"]})
    out = fill_missing(df, {"a": 0.0, "b": "unknown"})
    assert out["a"].tolist() == [1.0, 0.0]
    assert out["b"].tolist() == ["unknown", "x"]


def test_fill_missing_ignores_absent_columns():
    df = pd.DataFrame({"a": [1.0]})
    out = fill_missing(df, {"missing": 0.0})
    assert out.equals(df)
