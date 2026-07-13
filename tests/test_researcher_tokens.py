import json
import subprocess
import sys

from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.auth import authenticate_token, hash_token, verify_token
from rq_platform.settings import settings


client = TestClient(app)


def test_hash_and_verify_token():
    token_hash = hash_token("secret-token")

    assert token_hash != "secret-token"
    assert verify_token("secret-token", token_hash) is True
    assert verify_token("wrong", token_hash) is False


def test_legacy_api_token_still_works(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "api_token", "legacy-secret")
    monkeypatch.setattr(settings, "researcher_tokens_path", str(tmp_path / "researcher_tokens.json"))

    response = client.get("/status", headers={"X-API-Token": "legacy-secret"})

    assert response.status_code == 200


def test_researcher_token_authenticates(monkeypatch, tmp_path):
    token_path = _write_tokens(tmp_path, enabled=True)
    monkeypatch.setattr(settings, "api_token", "legacy-secret")
    monkeypatch.setattr(settings, "researcher_tokens_path", str(token_path))

    context = authenticate_token("researcher-secret")
    response = client.get("/status", headers={"X-API-Token": "researcher-secret"})

    assert context.researcher_id == "r001"
    assert context.researcher_name == "Researcher One"
    assert response.status_code == 200


def test_disabled_token_returns_403(monkeypatch, tmp_path):
    token_path = _write_tokens(tmp_path, enabled=False)
    monkeypatch.setattr(settings, "api_token", "legacy-secret")
    monkeypatch.setattr(settings, "researcher_tokens_path", str(token_path))

    response = client.get("/status", headers={"X-API-Token": "researcher-secret"})

    assert response.status_code == 403


def test_invalid_token_returns_401(monkeypatch, tmp_path):
    token_path = _write_tokens(tmp_path, enabled=True)
    monkeypatch.setattr(settings, "api_token", "legacy-secret")
    monkeypatch.setattr(settings, "researcher_tokens_path", str(token_path))

    response = client.get("/status", headers={"X-API-Token": "bad"})

    assert response.status_code == 401


def test_researcher_token_cli_create_list_disable_enable(tmp_path):
    config_path = tmp_path / "researcher_tokens.json"
    script = "scripts/33_manage_researcher_tokens.py"

    created = subprocess.run(
        [
            sys.executable,
            script,
            "--config",
            str(config_path),
            "create",
            "--researcher-id",
            "r001",
            "--name",
            "Researcher One",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "token=" in created.stdout
    data = json.loads(config_path.read_text(encoding="utf-8"))
    assert data[0]["token_hash"]
    assert "token" not in data[0]

    listed = subprocess.run(
        [sys.executable, script, "--config", str(config_path), "list"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Researcher One" in listed.stdout
    assert data[0]["token_hash"] not in listed.stdout

    subprocess.run(
        [sys.executable, script, "--config", str(config_path), "disable", "--researcher-id", "r001"],
        check=True,
    )
    assert json.loads(config_path.read_text(encoding="utf-8"))[0]["enabled"] is False

    subprocess.run(
        [sys.executable, script, "--config", str(config_path), "enable", "--researcher-id", "r001"],
        check=True,
    )
    assert json.loads(config_path.read_text(encoding="utf-8"))[0]["enabled"] is True


def _write_tokens(tmp_path, enabled=True):
    token_path = tmp_path / "researcher_tokens.json"
    token_path.write_text(
        json.dumps(
            [
                {
                    "researcher_id": "r001",
                    "name": "Researcher One",
                    "token_hash": hash_token("researcher-secret"),
                    "enabled": enabled,
                    "note": "test",
                }
            ]
        ),
        encoding="utf-8",
    )
    return token_path
