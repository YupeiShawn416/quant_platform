import pandas as pd

from strategy_research.factor import compute_factor


def test_compute_factor_outputs_standard_columns():
    market = pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-03"],
            "order_book_id": ["AAA.X", "AAA.X"],
            "close": [10.0, 11.0],
            "volume": [100, 100],
            "amount": [1000, 1100],
        }
    )
    result = compute_factor(market, {"run": {}})
    assert {"trade_date", "order_book_id", "factor_value"}.issubset(result.columns)
