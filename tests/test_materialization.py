from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from feaststore.materialization import MaterializationEngine


class FakeOffline:
    def __init__(self, df: pd.DataFrame) -> None:
        self._df = df

    def get_latest_rows(self, view, cutoff=None):
        return self._df.copy()


class RecordingOnline:
    def __init__(self) -> None:
        self.writes: list[tuple] = []

    def write_batch(self, view, rows, event_timestamps):
        self.writes.append((view.name, rows, event_timestamps))
        return len(rows)


def test_materialize_writes_latest_rows(driver_view):
    df = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "conv_rate": [0.5, 0.6],
            "acc_rate": [0.9, 0.8],
            "avg_daily_trips": [10, 20],
            "event_timestamp": pd.to_datetime(["2025-01-01", "2025-01-02"]),
        }
    )
    online = RecordingOnline()
    engine = MaterializationEngine(FakeOffline(df), online)

    result = engine.materialize(driver_view, cutoff=datetime(2025, 2, 1, tzinfo=timezone.utc))

    assert result.rows_written == 2
    name, rows, timestamps = online.writes[0]
    assert name == "driver_hourly_stats"
    assert "event_timestamp" not in rows[0]  # timestamp is pulled out separately
    assert len(timestamps) == 2


def test_materialize_empty_source_is_noop(driver_view):
    empty = pd.DataFrame(
        columns=["driver_id", "conv_rate", "acc_rate", "avg_daily_trips", "event_timestamp"]
    )
    online = RecordingOnline()
    engine = MaterializationEngine(FakeOffline(empty), online)
    result = engine.materialize(driver_view)
    assert result.rows_written == 0
    assert online.writes == []
