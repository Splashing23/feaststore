"""Small feature-engineering helpers for building offline feature tables.

These are pandas-side transforms a user runs when preparing the source table that
a FeatureView reads from. They are intentionally decoupled from the store: they
take and return DataFrames so they compose with whatever ETL a team already has.

The one non-obvious piece is `windowed_aggregate`, which does a time-windowed
aggregation per entity without an O(n^2) blowup by using a sorted merge_asof-style
pass per window.
"""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

_AGG_FUNCS: dict[str, Callable[[pd.Series], float]] = {
    "sum": lambda s: float(s.sum()),
    "mean": lambda s: float(s.mean()),
    "max": lambda s: float(s.max()),
    "min": lambda s: float(s.min()),
    "count": lambda s: float(s.count()),
}


def windowed_aggregate(
    df: pd.DataFrame,
    *,
    entity_col: str,
    timestamp_col: str,
    value_col: str,
    window: str,
    agg: str = "sum",
    output_col: str | None = None,
) -> pd.DataFrame:
    """Trailing time-windowed aggregate of `value_col` per entity.

    For each row, aggregate `value_col` over all rows for the same entity within
    the trailing `window` (a pandas offset string like ``"7d"`` or ``"1h"``),
    inclusive of the current row. Returns `df` with an added aggregate column.
    """
    if agg not in _AGG_FUNCS:
        raise ValueError(f"unsupported agg {agg!r}; choose from {sorted(_AGG_FUNCS)}")

    output_col = output_col or f"{value_col}_{agg}_{window}"
    out = df.sort_values([entity_col, timestamp_col]).copy()
    out[timestamp_col] = pd.to_datetime(out[timestamp_col])

    # rolling on a time index handles the trailing window efficiently (C-level).
    def _per_entity(group: pd.DataFrame) -> pd.Series:
        indexed = group.set_index(timestamp_col)[value_col]
        rolled = indexed.rolling(window).agg(agg)
        return rolled.reset_index(drop=True)

    rolled_values: list[float] = []
    for _, group in out.groupby(entity_col, sort=False):
        rolled_values.extend(_per_entity(group).tolist())
    out[output_col] = rolled_values
    return out


def fill_missing(df: pd.DataFrame, columns: dict[str, float | int | str]) -> pd.DataFrame:
    """Fill NaNs with explicit per-column defaults.

    Feature values fed to the online store should be dense; leaving NaNs turns
    into ``null`` at serving time and forces every consumer to handle it. Filling
    with a documented default at feature-build time is usually the right call.
    """
    out = df.copy()
    for col, default in columns.items():
        if col in out.columns:
            out[col] = out[col].fillna(default)
    return out
