import json

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.backtest.run_registry import BacktestRunRegistry, build_run_record
from rq_platform.backtest.run_store import BacktestRunStore
from rq_platform.settings import settings


client = TestClient(app)


def test_backtest_runs_api_lists_reads_downloads_and_cleans_up(tmp_path, monkeypatch):
    _patch_run_paths(tmp_path, monkeypatch)
    run_dir = _write_result_dir(tmp_path / "result", "api_run")
    cache_dir = BacktestRunStore().save_result_to_cache("api_run", run_dir)
    BacktestRunRegistry().append(
        build_run_record(
            run_id="api_run",
            config={"strategy_name": "API Run", "start_date": "2025-01-02", "end_date": "2025-12-31"},
            summary={"run_id": "api_run", "total_return": 0.1, "sharpe": 1.2, "max_drawdown": -0.03},
            mode="weights",
            status="success",
            result_dir=cache_dir,
            result_available=True,
        )
    )

    runs = client.get("/backtests/runs")
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "api_run"

    detail = client.get("/backtests/runs/api_run")
    assert detail.status_code == 200
    assert detail.json()["result_urls"]["dashboard"] == "/ui/backtests/runs/api_run"

    summary = client.get("/backtests/runs/api_run/summary")
    assert summary.status_code == 200
    assert summary.json()["run_id"] == "api_run"

    nav = client.get("/backtests/runs/api_run/nav")
    assert nav.status_code == 200
    assert nav.json()["count"] == 1

    download = client.get("/backtests/runs/api_run/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"

    BacktestRunRegistry().update("api_run", expires_at="2025-01-01T00:00:00Z")
    cleanup = client.post("/backtests/runs/cleanup")
    assert cleanup.status_code == 200
    assert cleanup.json()["deleted"] == ["api_run"]

    expired = client.get("/backtests/runs/api_run/summary")
    assert expired.status_code == 410


def test_backtest_runs_api_returns_404_for_unknown_run(tmp_path, monkeypatch):
    _patch_run_paths(tmp_path, monkeypatch)
    response = client.get("/backtests/runs/missing/summary")
    assert response.status_code == 404


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
        json.dumps({"run_id": run_id, "strategy_name": "API Run", "total_return": 0.1}),
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
