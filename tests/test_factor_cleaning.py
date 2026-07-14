import pandas as pd

from rq_platform.factors.factor_cleaning import clean_factor_values


def test_winsorize_and_zscore_by_date():
    frame = pd.DataFrame(
        {
            "trade_date": ["2026-01-01"] * 4,
            "order_book_id": ["a", "b", "c", "d"],
            "factor_value": [1.0, 2.0, 3.0, 100.0],
        }
    )
    result = clean_factor_values(frame)
    assert "factor_value_winsorized" in result.columns
    assert "factor_score" in result.columns
    assert abs(result["factor_score"].mean()) < 1e-9

