from __future__ import annotations

import numpy as np
import pandas as pd


DEMO_SYMBOLS = ["000001.XSHE", "600000.XSHG", "000858.XSHE", "600519.XSHG", "300750.XSHE", "601318.XSHG"]


def load_market_data(config: dict) -> pd.DataFrame:
    run = config["run"]
    dates = pd.bdate_range(run["start_date"], run["end_date"])
    rows = []
    for symbol_index, symbol in enumerate(DEMO_SYMBOLS):
        base = 10.0 + symbol_index * 7.5
        for day_index, trade_date in enumerate(dates):
            trend = 1.0 + 0.0015 * day_index
            cycle = 0.03 * np.sin(day_index / 3.0 + symbol_index)
            close = round(base * trend * (1.0 + cycle), 4)
            volume = int(800000 + symbol_index * 50000 + day_index * 1000)
            rows.append(
                {
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "order_book_id": symbol,
                    "close": close,
                    "volume": volume,
                    "amount": round(close * volume, 2),
                }
            )
    return pd.DataFrame(rows)


def load_universe(config: dict) -> pd.DataFrame:
    return pd.DataFrame({"order_book_id": DEMO_SYMBOLS})


def load_benchmark(config: dict) -> pd.DataFrame:
    run = config["run"]
    dates = pd.bdate_range(run["start_date"], run["end_date"])
    values = [1000.0 * (1.0 + 0.0008 * index) for index, _ in enumerate(dates)]
    return pd.DataFrame(
        {
            "trade_date": [date.strftime("%Y-%m-%d") for date in dates],
            "benchmark": run.get("benchmark", "000300.XSHG"),
            "benchmark_close": values,
        }
    )
