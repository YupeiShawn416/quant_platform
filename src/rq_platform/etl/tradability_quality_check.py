from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


KEY_COLUMNS = ["trade_date", "order_book_id"]


def check_tradability_dataset(year: int = 2025, data_root: Path | None = None) -> dict:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    path = root / "tradability_1d" / f"year={year}.parquet"
    result = {
        "dataset": "tradability_1d",
        "file_exists": path.exists(),
        "rows": 0,
        "symbols": 0,
        "min_date": None,
        "max_date": None,
        "duplicate_keys": 0,
        "missing_can_buy": 0,
        "missing_can_sell": 0,
        "cannot_buy": 0,
        "cannot_sell": 0,
        "reason_counts": {},
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
    if "can_buy" in frame.columns:
        can_buy = frame["can_buy"]
        result["missing_can_buy"] = int(can_buy.isna().sum())
        result["cannot_buy"] = int((~can_buy.astype(bool)).sum())
    if "can_sell" in frame.columns:
        can_sell = frame["can_sell"]
        result["missing_can_sell"] = int(can_sell.isna().sum())
        result["cannot_sell"] = int((~can_sell.astype(bool)).sum())
    if "reason" in frame.columns:
        reasons = frame["reason"].fillna("").astype(str)
        counts: dict[str, int] = {}
        for value in reasons[reasons != ""]:
            for reason in value.split(";"):
                counts[reason] = counts.get(reason, 0) + 1
        result["reason_counts"] = dict(sorted(counts.items()))
    return result


def print_tradability_check(result: dict) -> None:
    print(f"{result['dataset']} 检查结果")
    for key, value in result.items():
        if key != "dataset":
            print(f"  {key}: {value}")


def _date_or_none(value) -> str | None:
    if pd.isna(value):
        return None
    return pd.Timestamp(value).strftime("%Y-%m-%d")
