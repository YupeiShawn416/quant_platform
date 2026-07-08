from __future__ import annotations

import pandas as pd


def generate_signal(factor_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    frame = factor_df.copy()
    frame["signal_score"] = pd.to_numeric(frame["factor_value"], errors="coerce").fillna(0.0)
    return frame[["trade_date", "order_book_id", "signal_score"]]
