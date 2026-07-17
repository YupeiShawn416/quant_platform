from __future__ import annotations

import numpy as np
import pandas as pd


def compare_factor_prefixes(
    prefix: pd.DataFrame,
    extended: pd.DataFrame,
    *,
    relative_tolerance: float = 1e-12,
    absolute_tolerance: float = 1e-12,
) -> pd.DataFrame:
    if not prefix.index.is_unique or not extended.index.is_unique:
        raise ValueError("technical factor observations must have unique indexes")
    if set(prefix.columns) != set(extended.columns):
        raise ValueError("technical factor responses have different factor columns")
    overlap = prefix.index.intersection(extended.index)
    if len(overlap) != len(prefix.index):
        raise ValueError("extended response does not contain the full prefix index")
    left = prefix.loc[overlap].sort_index()
    right = extended.loc[overlap, left.columns].sort_index()
    rows = []
    for factor_id in sorted(left.columns.astype(str)):
        before = pd.to_numeric(left[factor_id], errors="coerce").to_numpy(dtype=float)
        after = pd.to_numeric(right[factor_id], errors="coerce").to_numpy(dtype=float)
        equal = np.isclose(
            before, after, rtol=relative_tolerance, atol=absolute_tolerance, equal_nan=True,
        )
        rows.append({
            "factor_id": factor_id,
            "prefix_stable": bool(equal.all()),
            "comparison_count": int(len(equal)),
            "mismatch_count": int((~equal).sum()),
            "max_absolute_difference": _max_difference(before, after),
        })
    return pd.DataFrame(rows)


def _max_difference(before: np.ndarray, after: np.ndarray) -> float:
    comparable = np.isfinite(before) & np.isfinite(after)
    if not comparable.any():
        return 0.0
    return float(np.max(np.abs(before[comparable] - after[comparable])))
