from __future__ import annotations

import pandas as pd


def compute_momentum_factor(prices: pd.DataFrame, lookback_days: int) -> pd.DataFrame:
    required = {"trade_date", "order_book_id", "close"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"prices missing required columns: {sorted(missing)}")

    frame = prices.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["order_book_id", "trade_date"])
    frame["factor_value"] = frame.groupby("order_book_id")["close"].pct_change(lookback_days)
    frame["factor_name"] = "momentum_20d"
    frame["factor_version"] = "v1"
    return frame[
        ["trade_date", "order_book_id", "factor_name", "factor_version", "factor_value"]
    ]
