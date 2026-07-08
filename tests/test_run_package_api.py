import json

import pandas as pd
from fastapi.testclient import TestClient

import rq_platform.api.main as api_main
from rq_platform.api.main import app
from rq_platform.backtest.current_store import CurrentBacktestStore
from rq_platform.settings import settings


client = TestClient(app)


def test_run_package_rejects_non_zip(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")

    response = client.post(
        "/backtests/run-package",
        files={"file": ("strategy.txt", b"not zip", "text/plain")},
    )

    assert response.status_code == 400
    assert "must be a .zip" in response.json()["detail"]


def test_run_package_sets_current_and_downloads_zip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(settings, "backtest_current_dir", str(tmp_path / "current"))
    monkeypatch.setattr(settings, "backtest_jobs_dir", str(tmp_path / "jobs"))

    class FakePackageManager:
        def run_package(self, package_path):
            assert package_path.name.lower().endswith(".zip")
            run_dir = tmp_path / "run"
            run_dir.mkdir()
            (run_dir / "summary.json").write_text(
                json.dumps({"run_id": "api_package_test", "total_return": 0.08}),
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
                "job_id": "job_package",
                "run_id": "api_package_test",
                "mode": "weights",
                "summary": {"run_id": "api_package_test", "total_return": 0.08},
                "warnings": [],
            }

    monkeypatch.setattr(api_main, "StrategyPackageJobManager", lambda: FakePackageManager())

    response = client.post(
        "/backtests/run-package",
        files={"file": ("strategy_package.ZIP", b"zip bytes", "application/zip")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    summary = client.get("/backtests/current/summary")
    assert summary.status_code == 200
    assert summary.json()["run_id"] == "api_package_test"
    nav = client.get("/backtests/current/nav")
    assert nav.json()["count"] == 1
    trades = client.get("/backtests/current/trades")
    assert trades.json()["count"] == 1
    download = client.get("/backtests/current/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
