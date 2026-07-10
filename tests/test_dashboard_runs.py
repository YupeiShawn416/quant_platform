import json

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.backtest.run_registry import BacktestRunRegistry, build_run_record
from rq_platform.backtest.run_store import BacktestRunStore
from rq_platform.settings import settings


client = TestClient(app)


def test_runs_dashboard_pages_open(tmp_path, monkeypatch):
    _patch_run_paths(tmp_path, monkeypatch)
    run_dir = _write_result_dir(tmp_path / "result", "dash_run")
    cache_dir = BacktestRunStore().save_result_to_cache("dash_run", run_dir)
    BacktestRunRegistry().append(
        build_run_record(
            run_id="dash_run",
            config={"strategy_name": "Dash Run"},
            summary={"run_id": "dash_run", "strategy_name": "Dash Run", "total_return": 0.2},
            mode="weights",
            status="success",
            result_dir=cache_dir,
            result_available=True,
        )
    )

    runs = client.get("/ui/backtests/runs")
    assert runs.status_code == 200
    assert "dash_run" in runs.text

    detail = client.get("/ui/backtests/runs/dash_run")
    assert detail.status_code == 200
    assert "Dash Run" in detail.text

    nav = client.get("/ui/backtests/runs/dash_run/nav")
    assert nav.status_code == 200
    assert "Backtest Dashboard" in nav.text


def test_runs_dashboard_expired_message(tmp_path, monkeypatch):
    _patch_run_paths(tmp_path, monkeypatch)
    BacktestRunRegistry().append(
        {
            "run_id": "expired_run",
            "status": "success",
            "result_available": False,
            "result_expired": True,
        }
    )

    response = client.get("/ui/backtests/runs/expired_run")

    assert response.status_code == 200
    assert "result files are no longer available" in response.text


def _patch_run_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(
        settings,
        "backtest_run_registry_path",
        str(tmp_path / "registry" / "backtest_runs.jsonl"),
    )
    monkeypatch.setattr(settings, "backtest_run_cache_dir", str(tmp_path / "cache"))


def _write_result_dir(path, run_id):
    path.mkdir()
    (path / "summary.json").write_text(
        json.dumps({"run_id": run_id, "strategy_name": "Dash Run", "total_return": 0.2}),
        encoding="utf-8",
    )
    pd.DataFrame({"trade_date": ["2025-01-02"], "strategy_nav": [1.0]}).to_csv(
        path / "nav.csv", index=False
    )
    pd.DataFrame({"trade_date": ["2025-01-02"], "total_value": [100]}).to_csv(
        path / "daily_account.csv", index=False
    )
    pd.DataFrame({"trade_date": ["2025-01-02"], "order_book_id": ["000001.XSHE"]}).to_csv(
        path / "positions.csv", index=False
    )
    pd.DataFrame({"trade_date": ["2025-01-02"], "side": ["BUY"]}).to_csv(
        path / "trades.csv", index=False
    )
    pd.DataFrame({"trade_date": ["2025-01-02"], "status": ["filled"]}).to_csv(
        path / "orders.csv", index=False
    )
    (path / "logs.txt").write_text("ok\n", encoding="utf-8")
    return path
