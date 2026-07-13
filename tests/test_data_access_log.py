import json

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.auth import hash_token
from rq_platform.settings import settings


client = TestClient(app)


def test_data_access_log_records_researcher_without_token(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    _write_fixture(tmp_path)
    _write_tokens(tmp_path)

    response = client.get(
        "/data/query/prices_1d_pre",
        params={"start_date": "2025-01-02", "end_date": "2025-01-02"},
        headers={"X-API-Token": "researcher-secret"},
    )

    assert response.status_code == 200
    log_path = tmp_path / "runs" / "data_access_log.jsonl"
    payload = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert payload["researcher_id"] == "r001"
    assert payload["researcher_name"] == "Researcher One"
    assert payload["dataset"] == "prices_1d_pre"
    assert payload["returned_rows"] == 1
    assert "researcher-secret" not in log_path.read_text(encoding="utf-8")


def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "legacy-secret")
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "rqdata"))
    monkeypatch.setattr(settings, "data_access_log_path", str(tmp_path / "runs" / "data_access_log.jsonl"))
    monkeypatch.setattr(settings, "researcher_tokens_path", str(tmp_path / "researcher_tokens.json"))


def _write_tokens(tmp_path):
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
            "trade_date": ["2025-01-02"],
            "order_book_id": ["000001.XSHE"],
            "close": [10.0],
        }
    ).to_parquet(root / "prices_1d_pre" / "year=2025.parquet", index=False)
