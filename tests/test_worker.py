import json

import pytest

from rq_platform.backtest import worker


def test_worker_success_writes_summary(tmp_path, monkeypatch):
    class FakeEngine:
        def __init__(self, config, strategy_path):
            self.config = config

        def run(self):
            run_dir = tmp_path / "runs" / self.config["run_id"]
            run_dir.mkdir(parents=True)
            (run_dir / "summary.json").write_text(
                json.dumps({"run_id": self.config["run_id"]}), encoding="utf-8"
            )
            return {"run_id": self.config["run_id"], "run_dir": str(run_dir)}

    monkeypatch.setattr(worker, "DailyBacktestEngine", FakeEngine)
    config_path, strategy_path = _write_worker_inputs(tmp_path)

    result = worker.run_worker(config_path, strategy_path, tmp_path / "runs")

    assert result["run_id"] == "worker_test"
    assert (tmp_path / "runs" / "worker_test" / "summary.json").exists()


def test_worker_failure_writes_error(tmp_path, monkeypatch):
    class FailingEngine:
        def __init__(self, config, strategy_path):
            self.config = config

        def run(self):
            raise RuntimeError("boom")

    monkeypatch.setattr(worker, "DailyBacktestEngine", FailingEngine)
    config_path, strategy_path = _write_worker_inputs(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            "worker",
            "--config",
            str(config_path),
            "--strategy",
            str(strategy_path),
            "--output-root",
            str(tmp_path / "runs"),
        ],
    )

    assert worker.main() == 1
    error = json.loads((tmp_path / "runs" / "worker_test" / "error.json").read_text())
    assert error["error_type"] == "RuntimeError"
    assert (tmp_path / "runs" / "worker_test" / "logs.txt").exists()


def _write_worker_inputs(tmp_path):
    config_path = tmp_path / "config.json"
    strategy_path = tmp_path / "strategy.py"
    config_path.write_text(
        json.dumps(
            {
                "run_id": "worker_test",
                "strategy_name": "worker_strategy",
                "start_date": "2025-01-02",
                "end_date": "2025-01-03",
                "initial_cash": 100000,
            }
        ),
        encoding="utf-8",
    )
    strategy_path.write_text(
        "def generate_weights(context, data):\n    return {}\n",
        encoding="utf-8",
    )
    return config_path, strategy_path
