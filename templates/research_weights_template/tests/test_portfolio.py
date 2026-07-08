import pandas as pd

from strategy_research.portfolio import generate_weights


def test_generate_weights_selects_top_n_equal_weight():
    signal = pd.DataFrame(
        {
            "trade_date": ["2025-01-02"] * 3,
            "order_book_id": ["A", "B", "C"],
            "signal_score": [1.0, 3.0, 2.0],
        }
    )
    result = generate_weights(signal, {"portfolio": {"top_n": 2}})
    assert set(result["order_book_id"]) == {"B", "C"}
    assert round(result["target_weight"].sum(), 8) == 1.0
