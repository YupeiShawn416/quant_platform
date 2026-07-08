from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


KEY_COLUMNS = ["trade_date", "order_book_id", "industry_system", "industry_level"]


def check_industry_dataset(year: int = 2025, data_root: Path | None = None) -> dict:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    path = root / "industry_classification" / f"year={year}.parquet"
    result = {
        "dataset": "industry_classification",
        "file_exists": path.exists(),
        "rows": 0,
        "symbols": 0,
        "min_date": None,
        "max_date": None,
        "duplicate_keys": 0,
        "missing_industry_code": 0,
        "missing_industry_name": 0,
        "daily_symbol_count_min": 0,
        "daily_symbol_count_max": 0,
        "industry_count": 0,
    }
    if not path.exists():
        return result
    frame = pd.read_parquet(path)
    result["rows"] = int(len(frame))
    if frame.empty:
        return result
    result["symbols"] = int(frame["order_book_id"].nunique()) if "order_book_id" in frame.columns else 0
    if "trade_date" in frame.columns:
        dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        result["min_date"] = _date_or_none(dates.min())
        result["max_date"] = _date_or_none(dates.max())
    if set(KEY_COLUMNS).issubset(frame.columns):
        result["duplicate_keys"] = int(frame.duplicated(KEY_COLUMNS).sum())
    if "industry_code" in frame.columns:
        result["missing_industry_code"] = int(frame["industry_code"].isna().sum())
    if "industry_name" in frame.columns:
        result["missing_industry_name"] = int(frame["industry_name"].isna().sum())
        result["industry_count"] = int(frame["industry_name"].dropna().nunique())
    if {"trade_date", "order_book_id"}.issubset(frame.columns):
        counts = frame.groupby("trade_date")["order_book_id"].nunique()
        if not counts.empty:
            result["daily_symbol_count_min"] = int(counts.min())
            result["daily_symbol_count_max"] = int(counts.max())
    return result


def print_industry_check(result: dict) -> None:
    print(f"{result['dataset']} 检查结果")
    for key, value in result.items():
        if key != "dataset":
            print(f"  {key}: {value}")


def _date_or_none(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
