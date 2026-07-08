import json

import pandas as pd

from rq_platform.backtest.daily_engine import DailyBacktestEngine


class BenchmarkFakeDataLoader:
    def __init__(self, include_benchmark: bool):
        self.include_benchmark = include_benchmark
        self.price_frame = pd.DataFrame(
            [
                {"trade_date": "2025-01-02", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 10.0},
                {"trade_date": "2025-01-03", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 11.0},
                {"trade_date": "2025-01-06", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 12.0},
            ]
        )
        self.index_frame = pd.DataFrame(
            [
                {"trade_date": "2025-01-02", "order_book_id": "000300.XSHG", "close": 4000.0},
                {"trade_date": "2025-01-03", "order_book_id": "000300.XSHG", "close": 4040.0},
                {"trade_date": "2025-01-06", "order_book_id": "000300.XSHG", "close": 4080.0},
            ]
        )

    def load_prices(self, symbols, start, end, adjust_type="pre", fields=None):
        frame = self.price_frame[self.price_frame["order_book_id"].isin(symbols)].copy()
        if fields:
            return frame[["trade_date", "order_book_id", "adjust_type", *fields]]
        return frame

    def load_index_prices(self, index_ids=None, start_date=None, end_date=None):
        if not self.include_benchmark:
            return pd.DataFrame(columns=["trade_date", "order_book_id", "close"])
        return self.index_frame[self.index_frame["order_book_id"].isin(index_ids or [])].copy()


def test_daily_engine_uses_index_benchmark_when_available(tmp_path):
    run_dir = _run_engine(tmp_path, BenchmarkFakeDataLoader(include_benchmark=True))

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    nav = pd.read_csv(run_dir / "nav.csv")

    assert summary["benchmark"] == "000300.XSHG"
    assert summary["benchmark_missing"] is False
    assert summary["benchmark_fallback_used"] is False
    assert summary["benchmark_metrics_reliable"] is True
    assert summary["benchmark_warning"] is None
    assert nav["benchmark_nav"].tolist() == [1.0, 1.01, 1.02]


def test_daily_engine_falls_back_when_index_benchmark_missing(tmp_path):
    run_dir = _run_engine(
        tmp_path,
        BenchmarkFakeDataLoader(include_benchmark=False),
        run_id="missing_index_benchmark",
    )

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    nav = pd.read_csv(run_dir / "nav.csv")

    assert summary["benchmark_missing"] is True
    assert summary["benchmark_fallback_used"] is True
    assert summary["benchmark_metrics_reliable"] is False
    assert "Benchmark price data not found" in summary["benchmark_warning"]
    assert nav["benchmark_nav"].tolist() == [1.0, 1.0, 1.0]


def _run_engine(tmp_path, data_loader, run_id="index_benchmark"):
    strategy_path = tmp_path / f"{run_id}_strategy.py"
    strategy_path.write_text(
        "def generate_weights(context, data):\n"
        "    return {'AAA.X': 1.0}\n",
        encoding="utf-8",
    )
    config = {
        "run_id": run_id,
        "strategy_name": "benchmark_test",
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
    DailyBacktestEngine(config, strategy_path, data_loader=data_loader).run()
    return tmp_path / "runs" / run_id
