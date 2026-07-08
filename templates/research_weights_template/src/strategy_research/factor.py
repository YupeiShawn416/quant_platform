from __future__ import annotations

import pandas as pd


def compute_factor(market_data: pd.DataFrame, config: dict) -> pd.DataFrame:
    frame = market_data.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.sort_values(["order_book_id", "trade_date"])
    frame["factor_value"] = frame.groupby("order_book_id")["close"].pct_change(5)
    frame["factor_value"] = frame["factor_value"].fillna(0.0)
    frame["trade_date"] = frame["trade_date"].dt.strftime("%Y-%m-%d")
    frame["factor_name"] = "demo_5d_momentum"
    frame["factor_version"] = "v1"
    return frame[["trade_date", "order_book_id", "factor_value", "factor_name", "factor_version"]]
