from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_factor_test_lake(root: Path) -> None:
    dates = pd.bdate_range("2026-05-01", periods=50).strftime("%Y-%m-%d").tolist()
    symbols = [f"00000{i}.XSHE" for i in range(1, 7)]
    price_rows = []
    valuation_rows = []
    component_rows = []
    for date_idx, trade_date in enumerate(dates):
        for symbol_idx, symbol in enumerate(symbols):
            close = 10 + symbol_idx + date_idx * (0.04 + symbol_idx * 0.01)
            price_rows.append({"trade_date": trade_date, "order_book_id": symbol, "close": close})
            valuation_rows.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": symbol,
                    "market_cap": 1000 + symbol_idx * 100 + date_idx,
                    "turnover_rate": 0.01 + symbol_idx * 0.001,
                }
            )
            if symbol_idx < 3:
                component_rows.append({"trade_date": trade_date, "index_id": "000300.XSHG", "order_book_id": symbol})
    (root / "prices_1d_pre").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(price_rows).to_parquet(root / "prices_1d_pre" / "year=2026.parquet", index=False)
    (root / "valuation_1d").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(valuation_rows).to_parquet(root / "valuation_1d" / "year=2026.parquet", index=False)
    (root / "index_components").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(component_rows).to_parquet(root / "index_components" / "year=2026.parquet", index=False)

