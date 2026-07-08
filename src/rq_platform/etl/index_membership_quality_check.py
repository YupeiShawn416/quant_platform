from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.etl.update_index_membership import DEFAULT_INDEX_IDS
from rq_platform.settings import settings


def check_index_membership_dataset(
    year: int = 2025,
    data_root: Path | None = None,
    expected_index_ids: list[str] | None = None,
) -> dict:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    expected = list(expected_index_ids or DEFAULT_INDEX_IDS)
    component_path = root / "index_components" / f"year={year}.parquet"
    weight_path = root / "index_weights" / f"year={year}.parquet"
    result = {
        "component_file_exists": component_path.exists(),
        "weight_file_exists": weight_path.exists(),
        "component_rows": 0,
        "weight_rows": 0,
        "indices": 0,
        "expected_indices": len(expected),
        "missing_indices": expected,
        "min_date": None,
        "max_date": None,
        "component_duplicate_keys": 0,
        "weight_duplicate_keys": 0,
        "missing_weight": 0,
        "daily_component_count_min": {},
        "daily_component_count_max": {},
        "daily_weight_sum_min": {},
        "daily_weight_sum_max": {},
    }
    components = pd.read_parquet(component_path) if component_path.exists() else pd.DataFrame()
    weights = pd.read_parquet(weight_path) if weight_path.exists() else pd.DataFrame()
    result["component_rows"] = int(len(components))
    result["weight_rows"] = int(len(weights))
    frame = components if not components.empty else weights
    if frame.empty:
        return result

    found = sorted(frame["index_id"].dropna().astype(str).unique().tolist())
    result["indices"] = len(found)
    result["missing_indices"] = [index_id for index_id in expected if index_id not in found]
    if "trade_date" in frame.columns:
        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        result["min_date"] = _date_or_none(dates.min())
        result["max_date"] = _date_or_none(dates.max())
    if not components.empty:
        keys = ["trade_date", "index_id", "order_book_id"]
        result["component_duplicate_keys"] = int(components.duplicated(keys).sum())
        counts = components.groupby(["index_id", "trade_date"])["order_book_id"].nunique()
        if not counts.empty:
            result["daily_component_count_min"] = {
                str(index_id): int(values.min()) for index_id, values in counts.groupby(level=0)
            }
            result["daily_component_count_max"] = {
                str(index_id): int(values.max()) for index_id, values in counts.groupby(level=0)
            }
    if not weights.empty:
        keys = ["trade_date", "index_id", "order_book_id"]
        result["weight_duplicate_keys"] = int(weights.duplicated(keys).sum())
        result["missing_weight"] = int(weights["weight"].isna().sum()) if "weight" in weights.columns else len(weights)
        sums = weights.groupby(["index_id", "trade_date"])["weight"].sum()
        if not sums.empty:
            result["daily_weight_sum_min"] = {
                str(index_id): float(values.min()) for index_id, values in sums.groupby(level=0)
            }
            result["daily_weight_sum_max"] = {
                str(index_id): float(values.max()) for index_id, values in sums.groupby(level=0)
            }
    return result


def print_index_membership_check(result: dict) -> None:
    print("index_components/index_weights 检查结果")
    for key, value in result.items():
        print(f"  {key}: {value}")


def _date_or_none(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
