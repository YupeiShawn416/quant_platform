import pandas as pd

from rq_platform.backtest.weight_strategy import WeightFileStrategy


class Context:
    def __init__(self, current_date):
        self.current_date = current_date


def test_daily_target_returns_weights_for_date():
    strategy = WeightFileStrategy(_weights_df())

    weights = strategy.generate_weights(Context("2025-01-02"), None)

    assert weights == {"AAA.X": 0.5}


def test_daily_target_missing_date_returns_empty_dict():
    strategy = WeightFileStrategy(_weights_df(), weight_mode="daily_target")

    assert strategy.generate_weights(Context("2025-01-03"), None) == {}


def test_rebalance_only_missing_date_returns_none():
    strategy = WeightFileStrategy(_weights_df(), weight_mode="rebalance_only")

    assert strategy.generate_weights(Context("2025-01-03"), None) is None


def test_nan_and_zero_weights_are_ignored():
    frame = pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "order_book_id": "AAA.X", "target_weight": 0.0},
            {"trade_date": "2025-01-02", "order_book_id": "BBB.X", "target_weight": None},
            {"trade_date": "2025-01-02", "order_book_id": "CCC.X", "target_weight": 0.4},
        ]
    )
    strategy = WeightFileStrategy(frame)

    assert strategy.generate_weights(Context("2025-01-02"), None) == {"CCC.X": 0.4}


def _weights_df():
    return pd.DataFrame(
        [{"trade_date": "2025-01-02", "order_book_id": "AAA.X", "target_weight": 0.5}]
    )
