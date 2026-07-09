from __future__ import annotations

import pandas as pd


def factor_to_signal(factor: pd.DataFrame) -> pd.DataFrame:
    required = {"trade_date", "order_book_id", "factor_value"}
    missing = required - set(factor.columns)
    if missing:
        raise ValueError(f"factor missing required columns: {sorted(missing)}")

    signal = factor.copy()
    signal["signal_score"] = signal["factor_value"]
    return signal[["trade_date", "order_book_id", "signal_score"]]
