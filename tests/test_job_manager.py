import json

import pandas as pd
import pytest

import rq_platform.backtest.job_manager as job_manager_module
from rq_platform.backtest.job_manager import BacktestJobError, BacktestJobManager
from rq_platform.settings import settings


def test_job_manager_rejects_missing_config_fields(tmp_path, monkeypatch):
    _patch_backtest_dirs(tmp_path, monkeypatch)
    manager = BacktestJobManager()

    with pytest.raises(BacktestJobError, match="missing backtest config fields"):
        manager.run_backtest("def generate_weights(context, data):\n    return {}\n", {"run_id": "bad"})


def test_job_manager_rejects_large_strategy_code(tmp_path, monkeypatch):
    _patch_backtest_dirs(tmp_path, monkeypatch)
    manager = BacktestJobManager()

    with pytest.raises(BacktestJobError, match="200KB"):
        manager.run_backtest("x" * (201 * 1024), _config())


def test_job_manager_local_success_sets_current(tmp_path, monkeypatch):
    _patch_backtest_dirs(tmp_path, monkeypatch)

    def fake_run_worker(config_path, strategy_path, output_root):
        config = json.loads(config_path.read_text(encoding="utf-8"))
        run_dir = output_root / config["run_id"]
        run_dir.mkdir()
        (run_dir / "summary.json").write_text(
            json.dumps({"run_id": config["run_id"], "total_return": 0.1}),
            encoding="utf-8",
        )
        pd.DataFrame({"trade_date": ["2025-01-02"], "strategy_nav": [1.0]}).to_csv(
            run_dir / "nav.csv", index=False
        )
        pd.DataFrame({"trade_date": ["2025-01-02"], "side": ["BUY"]}).to_csv(
            run_dir / "trades.csv", index=False
        )
        pd.DataFrame({"trade_date": ["2025-01-02"], "quantity": [100]}).to_csv(
            run_dir / "positions.csv", index=False
        )
        (run_dir / "logs.txt").write_text("ok\n", encoding="utf-8")
        return {"run_id": config["run_id"], "run_dir": str(run_dir), "summary": {}}

    monkeypatch.setattr(job_manager_module, "run_worker", fake_run_worker)
    result = BacktestJobManager().run_backtest(_strategy_code(), _config())

    assert result["status"] == "success"
    assert result["run_id"] == "job_test"
    assert (tmp_path / "current" / "summary.json").exists()


def test_job_manager_failure_writes_error_to_current(tmp_path, monkeypatch):
    _patch_backtest_dirs(tmp_path, monkeypatch)

    def fake_run_worker(config_path, strategy_path, output_root):
        raise RuntimeError("boom")

    monkeypatch.setattr(job_manager_module, "run_worker", fake_run_worker)
    result = BacktestJobManager().run_backtest(_strategy_code(), _config())

    assert result["status"] == "failed"
    error = json.loads((tmp_path / "current" / "error.json").read_text())
    assert error["error_type"] == "RuntimeError"
    assert (tmp_path / "current" / "logs.txt").exists()


def _patch_backtest_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_current_dir", str(tmp_path / "current"))
    monkeypatch.setattr(settings, "backtest_jobs_dir", str(tmp_path / "jobs"))
    monkeypatch.setattr(settings, "backtest_execution_mode", "local")


def _strategy_code():
    return "def generate_weights(context, data):\n    return {'AAA.X': 1.0}\n"


def _config():
    return {
        "run_id": "job_test",
        "strategy_name": "job_strategy",
        "start_date": "2025-01-02",
        "end_date": "2025-01-03",
        "initial_cash": 100000,
        "adjust_type": "pre",
        "frequency": "daily",
        "commission_rate": 0.0003,
        "tax_rate": 0.001,
        "slippage_rate": 0.0001,
        "lot_size": 100,
        "price_field": "close",
    }
