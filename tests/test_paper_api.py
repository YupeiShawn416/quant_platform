from __future__ import annotations

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.settings import settings


def _configure(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    (data_root / "instruments").mkdir(parents=True)
    pd.DataFrame({"order_book_id": ["000001.XSHE", "600519.XSHG"]}).to_parquet(
        data_root / "instruments" / "instruments.parquet",
        index=False,
    )
    (data_root / "prices_1d_pre").mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "close": 10.0},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "close": 100.0},
        ]
    ).to_parquet(data_root / "prices_1d_pre" / "year=2026.parquet", index=False)
    (data_root / "tradability_1d").mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "can_buy": True, "can_sell": True},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "can_buy": True, "can_sell": True},
        ]
    ).to_parquet(data_root / "tradability_1d" / "year=2026.parquet", index=False)
    monkeypatch.setattr(settings, "data_root", str(data_root))
    monkeypatch.setattr(settings, "paper_accounts_dir", str(tmp_path / "accounts"))
    monkeypatch.setattr(settings, "paper_registry_path", str(tmp_path / "registry" / "paper_accounts.jsonl"))
    monkeypatch.setattr(settings, "api_token", "change_me")


def test_paper_api_flow(tmp_path, monkeypatch):
    _configure(tmp_path, monkeypatch)
    client = TestClient(app)

    response = client.post(
        "/paper/accounts",
        json={"paper_id": "api_paper", "strategy_name": "api demo", "initial_cash": 1000000},
    )
    assert response.status_code == 200
    assert response.json()["account"]["researcher_id"] == "admin"

    weights = tmp_path / "weights.csv"
    pd.DataFrame(
        [{"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "target_weight": 0.5}]
    ).to_csv(weights, index=False)
    with weights.open("rb") as file:
        upload = client.post(
            "/paper/accounts/api_paper/target-weights",
            files={"file": ("weights.csv", file, "text/csv")},
        )
    assert upload.status_code == 200

    run = client.post("/paper/accounts/api_paper/run-daily", json={"trade_date": "2026-07-10"})
    assert run.status_code == 200
    assert run.json()["status"] == "success"

    accounts = client.get("/paper/accounts")
    assert accounts.status_code == 200
    assert accounts.json()["count"] == 1
    assert client.get("/paper/accounts/api_paper/nav").json()["count"] == 1
    assert client.get("/paper/accounts/api_paper/positions").json()["count"] == 1
    assert client.get("/paper/accounts/api_paper/trades").json()["count"] == 1
    assert client.get("/paper/accounts/api_paper/orders").json()["count"] == 1
    assert client.get("/paper/accounts/api_paper/download").status_code == 200
