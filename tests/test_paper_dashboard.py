from __future__ import annotations

from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.paper.paper_account import PaperAccount
from rq_platform.paper.paper_registry import PaperAccountRegistry
from rq_platform.paper.paper_store import PaperAccountStore
from rq_platform.settings import settings


def test_paper_dashboard_pages(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "paper_accounts_dir", str(tmp_path / "accounts"))
    monkeypatch.setattr(settings, "paper_registry_path", str(tmp_path / "registry" / "paper_accounts.jsonl"))
    account = PaperAccount(
        paper_id="dash_paper",
        strategy_name="dash",
        researcher_id="r001",
        researcher_name="Researcher One",
        initial_cash=1000000,
    )
    PaperAccountStore().create_account(account)
    PaperAccountRegistry().upsert(account)

    client = TestClient(app)
    list_page = client.get("/ui/paper")
    detail_page = client.get("/ui/paper/dash_paper")

    assert list_page.status_code == 200
    assert "dash_paper" in list_page.text
    assert "Researcher One" in list_page.text
    assert detail_page.status_code == 200
    assert "模拟账户详情" in detail_page.text
