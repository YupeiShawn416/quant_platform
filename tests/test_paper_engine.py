from __future__ import annotations

import pandas as pd

from rq_platform.data.query_service import DataQueryService
from rq_platform.paper.paper_account import PaperAccount
from rq_platform.paper.paper_engine import PaperEngine
from rq_platform.paper.paper_registry import PaperAccountRegistry
from rq_platform.paper.paper_store import PaperAccountStore


def _write_data_lake(root):
    (root / "instruments").mkdir(parents=True)
    pd.DataFrame({"order_book_id": ["000001.XSHE", "600519.XSHG"]}).to_parquet(
        root / "instruments" / "instruments.parquet",
        index=False,
    )
    (root / "prices_1d_pre").mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "close": 10.0},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "close": 100.0},
        ]
    ).to_parquet(root / "prices_1d_pre" / "year=2026.parquet", index=False)
    (root / "tradability_1d").mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "can_buy": True, "can_sell": True},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "can_buy": True, "can_sell": True},
        ]
    ).to_parquet(root / "tradability_1d" / "year=2026.parquet", index=False)


def test_paper_engine_generates_nav_positions_orders_and_trades(tmp_path):
    data_root = tmp_path / "data"
    _write_data_lake(data_root)
    store = PaperAccountStore(tmp_path / "accounts")
    registry = PaperAccountRegistry(tmp_path / "registry" / "paper_accounts.jsonl")
    account = PaperAccount(
        paper_id="paper_demo",
        strategy_name="demo",
        researcher_id="r001",
        researcher_name="Researcher One",
        initial_cash=1000000,
    )
    store.create_account(account)
    registry.upsert(account)
    store.save_target_weights(
        "paper_demo",
        pd.DataFrame(
            [
                {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "target_weight": 0.5},
                {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "target_weight": 0.3},
            ]
        ),
    )

    result = PaperEngine(store=store, registry=registry, query_service=DataQueryService(data_root)).run_daily(
        "paper_demo",
        "2026-07-10",
    )

    assert result["status"] == "success"
    assert result["orders"] == 2
    assert result["trades"] == 2
    assert len(store.read_csv("paper_demo", "nav.csv")) == 1
    assert len(store.read_csv("paper_demo", "positions.csv")) == 2
    assert registry.get("paper_demo")["latest_trade_date"] == "2026-07-10"
