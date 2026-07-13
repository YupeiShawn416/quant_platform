import json

from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.auth import hash_token
from rq_platform.backtest.run_registry import BacktestRunRegistry, build_run_record
from rq_platform.settings import settings


client = TestClient(app)


def test_runs_dashboard_shows_researcher_filter_and_column(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    registry = BacktestRunRegistry()
    registry.append(
        build_run_record(
            run_id="visible_run",
            config={"strategy_name": "Visible"},
            status="success",
            researcher_id="r001",
            researcher_name="Researcher One",
            submitted_by="Researcher One",
        )
    )
    registry.append(
        build_run_record(
            run_id="hidden_run",
            config={"strategy_name": "Hidden"},
            status="success",
            researcher_id="r002",
            researcher_name="Researcher Two",
            submitted_by="Researcher Two",
        )
    )

    response = client.get("/ui/backtests/runs?researcher_id=r001")

    assert response.status_code == 200
    assert "researcher_id" in response.text
    assert "Researcher One" in response.text
    assert "visible_run" in response.text
    assert "hidden_run" not in response.text


def test_researcher_usage_dashboard_shows_usage_stats(tmp_path, monkeypatch):
    _patch_paths(tmp_path, monkeypatch)
    _write_tokens(tmp_path)
    registry = BacktestRunRegistry()
    registry.append(
        build_run_record(
            run_id="success_run",
            config={"strategy_name": "Success"},
            status="success",
            researcher_id="r001",
            researcher_name="Researcher One",
            submitted_by="Researcher One",
        )
    )
    registry.append(
        build_run_record(
            run_id="failed_run",
            config={"strategy_name": "Failed"},
            status="failed",
            researcher_id="r001",
            researcher_name="Researcher One",
            submitted_by="Researcher One",
        )
    )

    response = client.get("/ui/researchers")

    assert response.status_code == 200
    assert "Researcher One" in response.text
    assert "Researcher Two" in response.text
    assert "r001" in response.text
    assert "r002" in response.text
    assert ">2</td>" in response.text
    assert ">1</td>" in response.text


def _patch_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(
        settings,
        "backtest_run_registry_path",
        str(tmp_path / "registry" / "backtest_runs.jsonl"),
    )
    monkeypatch.setattr(settings, "backtest_run_cache_dir", str(tmp_path / "cache"))
    monkeypatch.setattr(settings, "researcher_tokens_path", str(tmp_path / "researcher_tokens.json"))


def _write_tokens(tmp_path):
    (tmp_path / "researcher_tokens.json").write_text(
        json.dumps(
            [
                {
                    "researcher_id": "r001",
                    "name": "Researcher One",
                    "token_hash": hash_token("researcher-one"),
                    "enabled": True,
                    "note": "active",
                },
                {
                    "researcher_id": "r002",
                    "name": "Researcher Two",
                    "token_hash": hash_token("researcher-two"),
                    "enabled": False,
                    "note": "disabled",
                },
            ]
        ),
        encoding="utf-8",
    )
