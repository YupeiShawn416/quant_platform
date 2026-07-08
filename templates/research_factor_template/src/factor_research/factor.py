from __future__ import annotations

import pandas as pd


def compute_factor(config: dict) -> pd.DataFrame:
    dates = pd.bdate_range(config["start_date"], config["end_date"])
    symbols = ["000001.XSHE", "600000.XSHG"]
    rows = []
    for date_index, trade_date in enumerate(dates):
        for symbol_index, symbol in enumerate(symbols):
            rows.append(
                {
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "order_book_id": symbol,
                    "factor_id": config["factor_id"],
                    "factor_value": float(date_index - symbol_index),
                    "factor_version": config.get("factor_version", "v1"),
                }
            )
    return pd.DataFrame(rows)
