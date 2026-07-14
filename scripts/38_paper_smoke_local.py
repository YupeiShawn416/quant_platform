from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.settings import settings


def _write_demo_lake(root: Path) -> None:
    (root / "instruments").mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"order_book_id": ["000001.XSHE", "600519.XSHG"], "listed_date": ["1991-04-03", "2001-08-27"]}).to_parquet(
        root / "instruments" / "instruments.parquet",
        index=False,
    )
    (root / "prices_1d_pre").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "close": 10.0},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "close": 100.0},
        ]
    ).to_parquet(root / "prices_1d_pre" / "year=2026.parquet", index=False)
    (root / "tradability_1d").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "can_buy": True, "can_sell": True},
            {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "can_buy": True, "can_sell": True},
        ]
    ).to_parquet(root / "tradability_1d" / "year=2026.parquet", index=False)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        data_root = tmp_path / "data"
        _write_demo_lake(data_root)
        settings.data_root = str(data_root)
        settings.paper_accounts_dir = str(tmp_path / "runs" / "paper_trading" / "accounts")
        settings.paper_registry_path = str(tmp_path / "runs" / "paper_trading" / "registry" / "paper_accounts.jsonl")
        settings.api_token = "change_me"

        from rq_platform.api.main import app

        client = TestClient(app)
        create = client.post("/paper/accounts", json={"paper_id": "smoke_paper", "strategy_name": "smoke", "initial_cash": 1000000})
        create.raise_for_status()
        weights_path = tmp_path / "weights.csv"
        pd.DataFrame(
            [
                {"trade_date": "2026-07-10", "order_book_id": "000001.XSHE", "target_weight": 0.5},
                {"trade_date": "2026-07-10", "order_book_id": "600519.XSHG", "target_weight": 0.3},
            ]
        ).to_csv(weights_path, index=False)
        with weights_path.open("rb") as file:
            upload = client.post("/paper/accounts/smoke_paper/target-weights", files={"file": ("weights.csv", file, "text/csv")})
        upload.raise_for_status()
        run = client.post("/paper/accounts/smoke_paper/run-daily", json={"trade_date": "2026-07-10"})
        run.raise_for_status()
        nav = client.get("/paper/accounts/smoke_paper/nav")
        nav.raise_for_status()
        print(f"status={run.json()['status']}")
        print(f"nav_count={nav.json()['count']}")
        print("paper smoke local passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
