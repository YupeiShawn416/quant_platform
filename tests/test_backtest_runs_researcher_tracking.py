import json

import pandas as pd
from fastapi.testclient import TestClient

import rq_platform.backtest.job_manager as job_manager_module
from rq_platform.api.main import app
from rq_platform.backtest.job_manager import BacktestJobManager
from rq_platform.backtest.run_registry import BacktestRunRegistry, build_run_record
from rq_platform.settings import settings


client = TestClient(app)


def test_job_manager_records_researcher_metadata(tmp_path, monkeypatch):
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
    result = BacktestJobManager().run_backtest(
        _strategy_code(),
        _config(),
        submitter={
            "researcher_id": "r001",
            "researcher_name": "Researcher One",
            "submitted_by": "Researcher One",
            "client_ip": "127.0.0.1",
            "user_agent": "pytest",
        },
    )

    record = BacktestRunRegistry().get(result["run_id"])
    assert record["researcher_id"] == "r001"
    assert record["researcher_name"] == "Researcher One"
    assert record["submitted_by"] == "Researcher One"
    assert record["client_ip"] == "127.0.0.1"
    assert record["user_agent"] == "pytest"


def test_backtest_runs_api_filters_by_researcher(tmp_path, monkeypatch):
    _patch_run_paths(tmp_path, monkeypatch)
    registry = BacktestRunRegistry()
    registry.append(
        build_run_record(
            run_id="run_one",
            config={"strategy_name": "One"},
            status="success",
            researcher_id="r001",
            researcher_name="Researcher One",
            submitted_by="Researcher One",
        )
    )
    registry.append(
        build_run_record(
            run_id="run_two",
            config={"strategy_name": "Two"},
            status="failed",
            researcher_id="r002",
            researcher_name="Researcher Two",
            submitted_by="Researcher Two",
        )
    )

    all_runs = client.get("/backtests/runs")
    by_id = client.get("/backtests/runs?researcher_id=r001")
    by_name = client.get("/backtests/runs?researcher_name=Two")

    assert all_runs.status_code == 200
    assert all_runs.json()[0]["researcher_id"]
    assert by_id.status_code == 200
    assert [item["run_id"] for item in by_id.json()] == ["run_one"]
    assert by_id.json()[0]["researcher_name"] == "Researcher One"
    assert by_name.status_code == 200
    assert [item["run_id"] for item in by_name.json()] == ["run_two"]


def _patch_backtest_dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(settings, "backtest_current_dir", str(tmp_path / "current"))
    monkeypatch.setattr(settings, "backtest_jobs_dir", str(tmp_path / "jobs"))
    _patch_run_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "backtest_execution_mode", "local")


def _patch_run_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(
        settings,
        "backtest_run_registry_path",
        str(tmp_path / "registry" / "backtest_runs.jsonl"),
    )
    monkeypatch.setattr(settings, "backtest_run_cache_dir", str(tmp_path / "cache"))


def _strategy_code():
    return "def generate_weights(context, data):\n    return {'AAA.X': 1.0}\n"


def _config():
    return {
        "run_id": "researcher_job_test",
        "strategy_name": "researcher_job_strategy",
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
