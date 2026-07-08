from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data_sources.rqdata_source import VALUATION_COLUMNS
from rq_platform.settings import settings


KEY_COLUMNS = ["trade_date", "order_book_id"]
VALUE_COLUMNS = [column for column in VALUATION_COLUMNS if column not in KEY_COLUMNS]


def check_valuation_dataset(year: int = 2025, data_root: Path | None = None) -> dict:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    path = root / "valuation_1d" / f"year={year}.parquet"
    result = {
        "dataset": "valuation_1d",
        "file_exists": path.exists(),
        "rows": 0,
        "symbols": 0,
        "min_date": None,
        "max_date": None,
        "duplicate_keys": 0,
        "daily_symbol_count_min": 0,
        "daily_symbol_count_max": 0,
        "missing_by_column": {column: 0 for column in VALUE_COLUMNS},
    }
    if not path.exists():
        return result

    frame = pd.read_parquet(path)
    result["rows"] = int(len(frame))
    if frame.empty:
        return result

    if "order_book_id" in frame.columns:
        result["symbols"] = int(frame["order_book_id"].nunique())
    if "trade_date" in frame.columns:
        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        result["min_date"] = _date_or_none(dates.min())
        result["max_date"] = _date_or_none(dates.max())
    if set(KEY_COLUMNS).issubset(frame.columns):
        result["duplicate_keys"] = int(frame.duplicated(KEY_COLUMNS).sum())
    missing = {}
    for column in VALUE_COLUMNS:
        missing[column] = int(frame[column].isna().sum()) if column in frame.columns else result["rows"]
    result["missing_by_column"] = missing
    if {"trade_date", "order_book_id"}.issubset(frame.columns):
        daily_counts = frame.groupby("trade_date")["order_book_id"].nunique()
        if not daily_counts.empty:
            result["daily_symbol_count_min"] = int(daily_counts.min())
            result["daily_symbol_count_max"] = int(daily_counts.max())
    return result


def print_valuation_check(result: dict) -> None:
    print(f"{result['dataset']} 检查结果")
    for key, value in result.items():
        if key != "dataset":
            print(f"  {key}: {value}")


def _date_or_none(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
