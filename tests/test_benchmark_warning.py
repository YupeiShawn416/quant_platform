import json

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.backtest.daily_engine import DailyBacktestEngine
from rq_platform.settings import settings
from rq_platform.web.dashboard_data import load_current_dashboard_data


client = TestClient(app)


class BenchmarkDataLoader:
    def __init__(self, include_benchmark: bool):
        rows = [
            {"trade_date": "2025-01-02", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 10.0},
            {"trade_date": "2025-01-03", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 11.0},
            {"trade_date": "2025-01-06", "order_book_id": "AAA.X", "adjust_type": "pre", "close": 12.0},
        ]
        if include_benchmark:
            rows.extend(
                [
                    {"trade_date": "2025-01-02", "order_book_id": "000300.XSHG", "adjust_type": "pre", "close": 100.0},
                    {"trade_date": "2025-01-03", "order_book_id": "000300.XSHG", "adjust_type": "pre", "close": 101.0},
                    {"trade_date": "2025-01-06", "order_book_id": "000300.XSHG", "adjust_type": "pre", "close": 102.0},
                ]
            )
        self.frame = pd.DataFrame(rows)

    def load_prices(self, symbols, start, end, adjust_type="pre", fields=None):
        return self.frame[self.frame["order_book_id"].isin(symbols)].copy()


def test_benchmark_missing_is_recorded_in_summary_and_manifest(tmp_path):
    result = _run_engine(tmp_path, include_benchmark=False, run_id="benchmark_missing")
    run_dir = tmp_path / "runs" / "benchmark_missing"

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result["summary"]["benchmark_missing"] is True
    assert summary["benchmark_fallback_used"] is True
    assert summary["benchmark_metrics_reliable"] is False
    assert "Benchmark price data not found" in summary["benchmark_warning"]
    assert manifest["benchmark"]["benchmark_missing"] is True


def test_benchmark_present_is_marked_reliable(tmp_path):
    _run_engine(tmp_path, include_benchmark=True, run_id="benchmark_present")
    run_dir = tmp_path / "runs" / "benchmark_present"

    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    nav = pd.read_csv(run_dir / "nav.csv")

    assert summary["benchmark_missing"] is False
    assert summary["benchmark_fallback_used"] is False
    assert summary["benchmark_metrics_reliable"] is True
    assert summary["benchmark_warning"] is None
    assert nav["benchmark_nav"].iloc[-1] == 1.02


def test_dashboard_overview_shows_benchmark_warning(tmp_path, monkeypatch):
    current = tmp_path / "current"
    current.mkdir()
    _write_current_summary(current, include_warning=True)
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(settings, "backtest_current_dir", str(current))

    response = client.get("/ui/backtests/current/overview")

    assert response.status_code == 200
    assert "基准行情缺失" in response.text
    assert "N/A / unreliable" in response.text


def test_dashboard_data_defaults_old_summary_fields(tmp_path, monkeypatch):
    current = tmp_path / "current"
    current.mkdir()
    _write_current_summary(current, include_warning=False, old_style=True)
    monkeypatch.setattr(settings, "backtest_current_dir", str(current))

    data = load_current_dashboard_data()

    assert data["summary"]["benchmark_missing"] is False
    assert data["summary"]["benchmark_fallback_used"] is False
    assert data["summary"]["benchmark_metrics_reliable"] is True


def _run_engine(tmp_path, include_benchmark: bool, run_id: str):
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
    return DailyBacktestEngine(
        config,
        strategy_path,
        data_loader=BenchmarkDataLoader(include_benchmark=include_benchmark),
    ).run()


def _write_current_summary(current, include_warning: bool, old_style: bool = False):
    summary = {
        "run_id": "current_warning",
        "strategy_name": "warning_test",
        "start_date": "2025-01-02",
        "end_date": "2025-01-06",
        "initial_cash": 100000,
        "final_value": 101000,
        "total_return": 0.01,
        "annual_return": 0.1,
        "annual_volatility": 0.2,
        "sharpe": 0.5,
        "max_drawdown": -0.01,
        "benchmark_return": 0.0,
        "benchmark_annual_return": 0.0,
        "excess_return": 0.01,
        "tracking_error": 0.1,
        "information_ratio": 1.0,
        "win_rate": 0.5,
        "trade_count": 1,
        "created_at": "2026-07-08T00:00:00",
    }
    if include_warning and not old_style:
        summary.update(
            {
                "benchmark": "000300.XSHG",
                "benchmark_missing": True,
                "benchmark_fallback_used": True,
                "benchmark_warning": "Benchmark price data not found; benchmark_nav fallback to 1.0.",
                "benchmark_metrics_reliable": False,
            }
        )
    (current / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02"],
            "strategy_nav": [1.0],
            "benchmark_nav": [1.0],
            "excess_nav": [1.0],
            "daily_return": [0.0],
            "benchmark_return": [0.0],
            "excess_return": [0.0],
            "drawdown": [0.0],
        }
    ).to_csv(current / "nav.csv", index=False)
