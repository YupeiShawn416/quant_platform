from __future__ import annotations

import pandas as pd


def validate_factor_df(df: pd.DataFrame) -> list[str]:
    return _validate_common(df, ["trade_date", "order_book_id", "factor_value"], "factor")


def validate_signal_df(df: pd.DataFrame) -> list[str]:
    return _validate_common(df, ["trade_date", "order_book_id", "signal_score"], "signal")


def validate_weights_df(df: pd.DataFrame) -> list[str]:
    messages = _validate_common(df, ["trade_date", "order_book_id", "target_weight"], "weights")
    if "target_weight" in df.columns:
        weights = pd.to_numeric(df["target_weight"], errors="coerce")
        if weights.isna().any():
            messages.append("ERROR: weights target_weight contains non-numeric values")
        if (weights < 0).any():
            messages.append("ERROR: weights contain negative target_weight")
        if {"trade_date", "target_weight"}.issubset(df.columns):
            frame = df.copy()
            frame["target_weight"] = weights
            sums = frame.groupby("trade_date")["target_weight"].sum()
            overweight = sums[sums > 1.0 + 1e-6]
            if not overweight.empty:
                dates = ", ".join(overweight.index.astype(str).tolist())
                messages.append(f"ERROR: daily target_weight sum exceeds 1.0: {dates}")
    return messages


def _validate_common(df: pd.DataFrame, required: list[str], name: str) -> list[str]:
    messages: list[str] = []
    if df.empty:
        messages.append(f"ERROR: {name} dataframe is empty")
        return messages
    missing = [column for column in required if column not in df.columns]
    if missing:
        messages.append(f"ERROR: {name} missing columns: {', '.join(missing)}")
        return messages
    if df[required].isna().any().any():
        messages.append(f"ERROR: {name} contains nulls in required columns")
    dates = pd.to_datetime(df["trade_date"], errors="coerce")
    if dates.isna().any():
        messages.append(f"ERROR: {name} trade_date contains invalid dates")
    ids = df["order_book_id"].astype(str).str.strip()
    if (ids == "").any():
        messages.append(f"ERROR: {name} order_book_id contains empty values")
    if df.duplicated(["trade_date", "order_book_id"]).any():
        messages.append(f"ERROR: {name} contains duplicate trade_date + order_book_id rows")
    return messages
