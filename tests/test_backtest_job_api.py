import json

import pandas as pd
from fastapi.testclient import TestClient

import rq_platform.api.main as api_main
from rq_platform.api.main import app
from rq_platform.backtest.current_store import CurrentBacktestStore
from rq_platform.settings import settings


client = TestClient(app)


def test_current_backtest_initially_missing(tmp_path, monkeypatch):
    _patch_current_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "api_token", "change_me")

    response = client.get("/backtests/current")

    assert response.status_code == 200
    assert response.json() == {"exists": False}


def test_run_backtest_missing_config_returns_400(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")

    response = client.post(
        "/backtests/run",
        json={"strategy_code": "def generate_weights(context, data):\n    return {}\n", "config": {}},
    )

    assert response.status_code == 400
    assert "missing backtest config fields" in response.json()["detail"]


def test_run_backtest_sets_current_and_delete_clears_it(tmp_path, monkeypatch):
    _patch_current_dir(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "api_token", "change_me")

    class FakeManager:
        def run_backtest(self, strategy_code, config, strategy_filename="strategy.py", submitter=None):
            run_dir = tmp_path / "run"
            run_dir.mkdir()
            (run_dir / "summary.json").write_text(
                json.dumps({"run_id": "api_test", "total_return": 0.2}),
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
            CurrentBacktestStore().set_current_from_run_dir(run_dir)
            return {
                "status": "success",
                "job_id": "job_001",
                "run_id": "api_test",
                "summary": {"run_id": "api_test", "total_return": 0.2},
            }

    monkeypatch.setattr(api_main, "BacktestJobManager", lambda: FakeManager())

    response = client.post(
        "/backtests/run",
        json={"strategy_code": "def generate_weights(context, data):\n    return {}\n", "config": {}},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    summary = client.get("/backtests/current/summary")
    assert summary.status_code == 200
    assert summary.json()["run_id"] == "api_test"

    nav = client.get("/backtests/current/nav")
    assert nav.status_code == 200
    assert nav.json()["count"] == 1

    deleted = client.delete("/backtests/current")
    assert deleted.status_code == 200
    assert deleted.json() == {"deleted": True}
    assert client.get("/backtests/current").json() == {"exists": False}


def _patch_current_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "backtest_current_dir", str(tmp_path / "current"))
