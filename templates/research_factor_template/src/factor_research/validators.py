from __future__ import annotations

import pandas as pd


REQUIRED_LONG_COLUMNS = ["trade_date", "order_book_id", "factor_id", "factor_value", "factor_version"]


def validate_factor_long(df: pd.DataFrame) -> list[str]:
    messages: list[str] = []
    missing = [column for column in REQUIRED_LONG_COLUMNS if column not in df.columns]
    if missing:
        messages.append(f"ERROR: missing columns: {', '.join(missing)}")
    if not missing and df[REQUIRED_LONG_COLUMNS].isna().any().any():
        messages.append("ERROR: factor_long contains nulls")
    return messages
