import pandas as pd

from strategy_research.signal import generate_signal


def test_generate_signal_outputs_standard_columns():
    factor = pd.DataFrame({"trade_date": ["2025-01-02"], "order_book_id": ["AAA.X"], "factor_value": [0.1]})
    result = generate_signal(factor, {})
    assert list(result.columns) == ["trade_date", "order_book_id", "signal_score"]
