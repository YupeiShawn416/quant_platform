from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


KEY_COLUMNS = ["trade_date", "order_book_id", "adjust_type"]


def check_price_dataset(
    adjust_type: str, year: int = 2025, data_root: Path | None = None
) -> dict:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    dataset = f"prices_1d_{adjust_type}"
    path = root / dataset / f"year={year}.parquet"
    result = {
        "dataset": dataset,
        "file_exists": path.exists(),
        "rows": 0,
        "symbols": 0,
        "min_date": None,
        "max_date": None,
        "duplicate_keys": 0,
        "missing_close": 0,
        "missing_volume": 0,
        "daily_symbol_count_min": 0,
        "daily_symbol_count_max": 0,
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
        trade_dates = pd.to_datetime(frame["trade_date"], errors="coerce")
        result["min_date"] = _date_or_none(trade_dates.min())
        result["max_date"] = _date_or_none(trade_dates.max())
    if set(KEY_COLUMNS).issubset(frame.columns):
        result["duplicate_keys"] = int(frame.duplicated(KEY_COLUMNS).sum())
    if "close" in frame.columns:
        result["missing_close"] = int(frame["close"].isna().sum())
    if "volume" in frame.columns:
        result["missing_volume"] = int(frame["volume"].isna().sum())
    if {"trade_date", "order_book_id"}.issubset(frame.columns):
        daily_counts = frame.groupby("trade_date")["order_book_id"].nunique()
        if not daily_counts.empty:
            result["daily_symbol_count_min"] = int(daily_counts.min())
            result["daily_symbol_count_max"] = int(daily_counts.max())
    return result


def check_all_price_datasets(
    year: int = 2025, data_root: Path | None = None
) -> list[dict]:
    return [
        check_price_dataset("pre", year=year, data_root=data_root),
        check_price_dataset("none", year=year, data_root=data_root),
    ]


def print_price_check(result: dict) -> None:
    title = f"{result['dataset']} 2025 检查结果"
    print(title)
    for key, value in result.items():
        if key != "dataset":
            print(f"  {key}: {value}")


def _date_or_none(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
