import pandas as pd

from rq_platform.backtest.daily_engine import DailyBacktestEngine


class FakeDataLoader:
    def __init__(self):
        self.frame = pd.DataFrame(
            [
                {"trade_date": "2025-01-02", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 10.0},
                {"trade_date": "2025-01-02", "order_book_id": "BBB.X", "adjust_type": "pre", "close": 20.0},
                {"trade_date": "2025-01-03", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 11.0},
                {"trade_date": "2025-01-03", "order_book_id": "BBB.X", "adjust_type": "pre", "close": 19.0},
                {"trade_date": "2025-01-06", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 12.0},
                {"trade_date": "2025-01-06", "order_book_id": "BBB.X", "adjust_type": "pre", "close": 18.0},
            ]
        )

    def load_prices(self, symbols, start, end, adjust_type="pre", fields=None):
        frame = self.frame[self.frame["order_book_id"].isin(symbols)].copy()
        if not symbols or symbols == ["000300.XSHG"]:
            return pd.DataFrame(columns=["trade_date", "order_book_id", "adjust_type", "close"])
        return frame


def test_daily_engine_runs_and_scales_weights(tmp_path):
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text(
        "def generate_weights(context, data):\n"
        "    return {'AAA.X': 0.8, 'BBB.X': 0.8}\n",
        encoding="utf-8",
    )
    config = _config(tmp_path)

    result = DailyBacktestEngine(config, strategy_path, data_loader=FakeDataLoader()).run()

    run_dir = tmp_path / "runs" / "daily_engine_test"
    assert result["run_id"] == "daily_engine_test"
    for filename in ["nav.csv", "daily_account.csv", "trades.csv", "positions.csv", "orders.csv"]:
        assert (run_dir / filename).exists()
    daily_account = pd.read_csv(run_dir / "daily_account.csv")
    assert (daily_account["total_value"] >= 0).all()
    assert daily_account["position_ratio"].max() <= 1.01


def test_daily_engine_empty_weights_clear_positions(tmp_path):
    strategy_path = tmp_path / "strategy.py"
    strategy_path.write_text(
        "def generate_weights(context, data):\n"
        "    if context.current_date == '2025-01-02':\n"
        "        return {'AAA.X': 1.0}\n"
        "    return {}\n",
        encoding="utf-8",
    )
    config = _config(tmp_path, run_id="daily_engine_empty_weights")

    DailyBacktestEngine(config, strategy_path, data_loader=FakeDataLoader()).run()

    positions = pd.read_csv(tmp_path / "runs" / "daily_engine_empty_weights" / "positions.csv")
    assert positions["trade_date"].max() == "2025-01-02"


def _config(tmp_path, run_id="daily_engine_test"):
    return {
        "run_id": run_id,
        "strategy_name": "unit_strategy",
        "start_date": "2025-01-02",
        "end_date": "2025-01-06",
        "initial_cash": 100000.0,
        "benchmark": "000300.XSHG",
        "adjust_type": "pre",
        "frequency": "daily",
        "commission_rate": 0.0003,
        "tax_rate": 0.001,
        "slippage_rate": 0.0001,
        "lot_size": 100,
        "price_field": "close",
        "output_root": str(tmp_path / "runs"),
    }
