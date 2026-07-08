from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.etl.update_index_prices import DEFAULT_INDEX_IDS
from rq_platform.settings import settings


KEY_COLUMNS = ["trade_date", "order_book_id"]


def check_index_price_dataset(
    year: int = 2025,
    data_root: Path | None = None,
    expected_index_ids: list[str] | None = None,
) -> dict:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    path = root / "index_prices_1d" / f"year={year}.parquet"
    expected = list(expected_index_ids or DEFAULT_INDEX_IDS)
    result = {
        "dataset": "index_prices_1d",
        "file_exists": path.exists(),
        "rows": 0,
        "indices": 0,
        "expected_indices": len(expected),
        "missing_indices": expected,
        "min_date": None,
        "max_date": None,
        "duplicate_keys": 0,
        "missing_close": 0,
        "daily_index_count_min": 0,
        "daily_index_count_max": 0,
        "per_index_rows": {},
        "per_index_close_missing": {},
    }
    if not path.exists():
        return result

    frame = pd.read_parquet(path)
    result["rows"] = int(len(frame))
    if frame.empty:
        return result

    if "order_book_id" in frame.columns:
        found = sorted(frame["order_book_id"].dropna().astype(str).unique().tolist())
        result["indices"] = len(found)
        result["missing_indices"] = [index_id for index_id in expected if index_id not in found]
        result["per_index_rows"] = {
            str(index_id): int(count)
            for index_id, count in frame.groupby("order_book_id").size().sort_index().items()
        }
    if "trade_date" in frame.columns:
        trade_dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        result["min_date"] = _date_or_none(trade_dates.min())
        result["max_date"] = _date_or_none(trade_dates.max())
    if set(KEY_COLUMNS).issubset(frame.columns):
        result["duplicate_keys"] = int(frame.duplicated(KEY_COLUMNS).sum())
    if "close" in frame.columns:
        result["missing_close"] = int(frame["close"].isna().sum())
        if "order_book_id" in frame.columns:
            missing = frame["close"].isna()
            result["per_index_close_missing"] = {
                str(index_id): int(count)
                for index_id, count in frame[missing].groupby("order_book_id").size().sort_index().items()
            }
    if {"trade_date", "order_book_id"}.issubset(frame.columns):
        daily_counts = frame.groupby("trade_date")["order_book_id"].nunique()
        if not daily_counts.empty:
            result["daily_index_count_min"] = int(daily_counts.min())
            result["daily_index_count_max"] = int(daily_counts.max())
    return result


def print_index_price_check(result: dict) -> None:
    title = f"{result['dataset']} 检查结果"
    print(title)
    for key, value in result.items():
        if key != "dataset":
            print(f"  {key}: {value}")


def _date_or_none(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
