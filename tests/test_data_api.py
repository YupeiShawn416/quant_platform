import json
import math

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.auth import hash_token
from rq_platform.settings import settings


client = TestClient(app)


def test_data_api_lists_coverage_schema_and_queries(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    _write_fixture(tmp_path)

    datasets = client.get("/data/datasets")
    coverage = client.get("/data/coverage")
    schema = client.get("/data/schema/prices_1d_pre")
    query = client.get(
        "/data/query/prices_1d_pre",
        params={
            "start_date": "2025-01-02",
            "end_date": "2025-01-03",
            "order_book_id": "000001.XSHE",
            "fields": "trade_date,order_book_id,close",
            "limit": 1,
            "offset": 0,
        },
    )

    assert datasets.status_code == 200
    assert any(item["dataset"] == "prices_1d_pre" for item in datasets.json()["datasets"])
    assert coverage.status_code == 200
    assert coverage.json()["supported_end_date"] == "2026-07-10"
    assert schema.status_code == 200
    assert {item["name"] for item in schema.json()["fields"]} >= {"trade_date", "close"}
    assert query.status_code == 200
    payload = query.json()
    assert payload["date_column"] == "trade_date"
    assert payload["row_count"] == 1
    assert payload["has_more"] is True
    assert payload["records"] == [
        {"trade_date": "2025-01-02", "order_book_id": "000001.XSHE", "close": 10.0}
    ]


def test_data_api_errors_and_csv(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    _write_fixture(tmp_path)

    too_large = client.get("/data/query/prices_1d_pre?limit=50001")
    zero_limit = client.get("/data/query/prices_1d_pre?limit=0")
    non_int_limit = client.get("/data/query/prices_1d_pre?limit=abc")
    bad_format = client.get("/data/query/prices_1d_pre?format=xlsx&limit=1")
    missing_dataset = client.get("/data/query/not_a_dataset")
    bad_field = client.get("/data/query/prices_1d_pre?fields=missing")
    csv_response = client.get("/data/query/prices_1d_pre?format=csv&limit=1")

    assert too_large.status_code == 400
    assert zero_limit.status_code == 400
    assert non_int_limit.status_code == 400
    assert bad_format.status_code == 400
    assert non_int_limit.json()["detail"]["error_code"] == "invalid_parameter"
    assert missing_dataset.status_code == 404
    assert bad_field.status_code == 400
    assert csv_response.status_code == 200
    assert csv_response.headers["content-type"].startswith("text/csv")
    assert "trade_date" in csv_response.text


def test_data_api_json_replaces_non_finite_values(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    (root / "financial_pit_field_pack" / "year=2026").mkdir(parents=True)
    pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE"] * 25,
            "report_period": ["2025q4"] * 25,
            "info_date": ["2026-04-30"] * 25,
            "revenue": [math.inf] + [float("nan")] + [100.0] * 23,
        }
    ).to_parquet(root / "financial_pit_field_pack" / "year=2026" / "financial_pit_field_pack.parquet", index=False)

    response = client.get(
        "/data/query/financial_pit_field_pack",
        params={
            "dates": "2026-04-30",
            "fields": "order_book_id,info_date,revenue",
            "limit": 25,
        },
    )

    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 25
    assert records[0]["revenue"] is None
    assert records[1]["revenue"] is None
    assert records[2]["revenue"] == 100.0


def test_data_api_filters_explicit_trade_dates(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    (root / "valuation_1d").mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2026-01-30", "2026-02-27", "2026-03-31"],
            "order_book_id": ["000001.XSHE"] * 3,
            "market_cap": [1.0, 2.0, 3.0],
        }
    ).to_parquet(root / "valuation_1d" / "year=2026.parquet", index=False)

    response = client.get(
        "/data/query/valuation_1d",
        params={
            "trade_date": "2026-01-30,2026-03-31",
            "order_book_id": "000001.XSHE",
            "fields": "trade_date,order_book_id,market_cap",
            "limit": 10,
        },
    )

    assert response.status_code == 200
    records = response.json()["records"]
    assert [item["trade_date"] for item in records] == ["2026-01-30", "2026-03-31"]


def test_data_api_researcher_token_and_invalid_token(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch, api_token="legacy-secret")
    _write_fixture(tmp_path)
    _write_researcher_tokens(tmp_path)

    ok = client.get("/data/datasets", headers={"X-API-Token": "researcher-secret"})
    bad = client.get("/data/datasets", headers={"X-API-Token": "bad-token"})

    assert ok.status_code == 200
    assert bad.status_code == 401


def _patch_paths(tmp_path, monkeypatch, api_token="change_me"):
    monkeypatch.setattr(settings, "api_token", api_token)
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "rqdata"))
    monkeypatch.setattr(settings, "data_access_log_path", str(tmp_path / "runs" / "data_access_log.jsonl"))
    monkeypatch.setattr(settings, "researcher_tokens_path", str(tmp_path / "researcher_tokens.json"))


def _write_researcher_tokens(tmp_path):
    (tmp_path / "researcher_tokens.json").write_text(
        json.dumps(
            [
                {
                    "researcher_id": "r001",
                    "name": "Researcher One",
                    "token_hash": hash_token("researcher-secret"),
                    "enabled": True,
                    "note": "test",
                }
            ]
        ),
        encoding="utf-8",
    )


def _write_fixture(tmp_path):
    root = tmp_path / "rqdata"
    (root / "prices_1d_pre").mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-03"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "close": [10.0, 10.2],
            "volume": [100, 110],
        }
    ).to_parquet(root / "prices_1d_pre" / "year=2025.parquet", index=False)
    (root / "trading_calendar").mkdir()
    pd.DataFrame({"trade_date": ["2025-01-02", "2025-01-03"]}).to_parquet(
        root / "trading_calendar" / "trading_calendar.parquet",
        index=False,
    )
