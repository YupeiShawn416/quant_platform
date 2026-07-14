from __future__ import annotations

import pandas as pd

from rq_platform.paper.paper_account import PaperAccount
from rq_platform.paper.paper_registry import PaperAccountRegistry
from rq_platform.paper.paper_store import PaperAccountStore


def test_paper_account_store_and_registry(tmp_path):
    store = PaperAccountStore(tmp_path / "accounts")
    registry = PaperAccountRegistry(tmp_path / "registry" / "paper_accounts.jsonl")
    account = PaperAccount(
        paper_id="paper/demo",
        strategy_name="demo",
        researcher_id="r001",
        researcher_name="Researcher One",
        initial_cash=1000000,
    )

    store.create_account(account)
    registry.upsert(account)
    loaded = store.read_account("paper_demo")

    assert loaded.paper_id == "paper_demo"
    assert store.exists("paper_demo")
    assert registry.get("paper_demo")["researcher_id"] == "r001"

    weights = pd.DataFrame(
        [{"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "target_weight": 0.5}]
    )
    store.save_target_weights("paper_demo", weights)
    zip_path = store.package_zip("paper_demo")

    assert zip_path.exists()
    assert store.delete("paper_demo")
