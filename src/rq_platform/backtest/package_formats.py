from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


STANDARD_WEIGHT_COLUMNS = ["trade_date", "order_book_id", "target_weight"]


def read_weights_file(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if source.suffix == ".parquet":
        frame = pd.read_parquet(source)
    elif source.suffix == ".csv":
        frame = pd.read_csv(source)
    else:
        raise ValueError(f"unsupported weights file type: {source.suffix}")
    return _standardize_weights_columns(frame)


def validate_weights_df(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[str]]:
    warnings: list[str] = []
    if df.empty:
        raise ValueError("weights file is empty")

    frame = _standardize_weights_columns(df)
    missing = [column for column in STANDARD_WEIGHT_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"weights file missing columns: {', '.join(missing)}")

    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce")
    if frame["trade_date"].isna().any():
        raise ValueError("weights trade_date contains invalid dates")
    frame["trade_date"] = frame["trade_date"].dt.strftime("%Y-%m-%d")
    frame["order_book_id"] = frame["order_book_id"].astype(str).str.strip()
    if (frame["order_book_id"] == "").any():
        raise ValueError("weights order_book_id cannot be empty")
    frame["target_weight"] = pd.to_numeric(frame["target_weight"], errors="coerce")
    if frame["target_weight"].isna().any():
        raise ValueError("weights target_weight must be numeric")
    if (frame["target_weight"] < 0).any():
        raise ValueError("weights target_weight cannot be negative in long-only V0")
    if frame.duplicated(["trade_date", "order_book_id"]).any():
        raise ValueError("weights contain duplicate trade_date + order_book_id rows")

    start_date = str(config.get("start_date"))
    end_date = str(config.get("end_date"))
    before = len(frame)
    frame = frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)]
    if len(frame) != before:
        warnings.append("weights outside start_date/end_date were filtered")
    if frame.empty:
        raise ValueError("weights contain no rows in backtest date range")

    tolerance = float(config.get("weight_tolerance", 1e-6))
    allow_normalization = bool(config.get("allow_weight_normalization", False))
    sums = frame.groupby("trade_date")["target_weight"].sum()
    overweight_dates = sums[sums > 1.0 + tolerance]
    if not overweight_dates.empty:
        if not allow_normalization:
            dates = ", ".join(overweight_dates.index.astype(str).tolist())
            raise ValueError(f"daily target_weight sum exceeds 1.0: {dates}")
        for trade_date, total in overweight_dates.items():
            mask = frame["trade_date"] == trade_date
            frame.loc[mask, "target_weight"] = frame.loc[mask, "target_weight"] / float(total)
        warnings.append("weights were normalized for dates with total weight above 1.0")

    return frame.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True), warnings


def weights_long_to_wide(df: pd.DataFrame) -> pd.DataFrame:
    frame = _standardize_weights_columns(df)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    wide = frame.pivot_table(
        index="trade_date",
        columns="order_book_id",
        values="target_weight",
        aggfunc="sum",
    )
    return wide.reset_index().rename_axis(columns=None)


def weights_wide_to_long(df: pd.DataFrame) -> pd.DataFrame:
    if "trade_date" not in df.columns:
        raise ValueError("wide weights must contain trade_date")
    long = df.melt(
        id_vars=["trade_date"],
        var_name="order_book_id",
        value_name="target_weight",
    )
    long["target_weight"] = pd.to_numeric(long["target_weight"], errors="coerce")
    long = long.dropna(subset=["target_weight"])
    long = long[long["target_weight"] != 0]
    long["trade_date"] = pd.to_datetime(long["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    return long[STANDARD_WEIGHT_COLUMNS].sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)


def _standardize_weights_columns(df: pd.DataFrame) -> pd.DataFrame:
    frame = pd.DataFrame(df).copy()
    rename_map = {column: str(column).strip() for column in frame.columns}
    frame = frame.rename(columns=rename_map)
    return frame
