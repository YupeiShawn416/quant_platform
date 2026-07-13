from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.settings import settings


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "rqdata"
        _write_fixture(root)
        original_data_root = settings.data_root
        original_log_path = settings.data_access_log_path
        try:
            settings.data_root = str(root)
            settings.data_access_log_path = str(Path(tmp) / "runs" / "data_access_log.jsonl")
            client = TestClient(app)
            datasets = client.get("/data/datasets")
            query = client.get(
                "/data/query/prices_1d_pre",
                params={
                    "start_date": "2025-01-02",
                    "end_date": "2025-01-03",
                    "order_book_id": "000001.XSHE",
                    "fields": "trade_date,order_book_id,close",
                },
            )
            datasets.raise_for_status()
            query.raise_for_status()
            payload = query.json()
            print(f"datasets={datasets.json()['count']}")
            print(f"rows={payload['row_count']}")
            print("data api smoke ok")
            return 0
        finally:
            settings.data_root = original_data_root
            settings.data_access_log_path = original_log_path


def _write_fixture(root: Path) -> None:
    (root / "trading_calendar").mkdir(parents=True)
    pd.DataFrame({"trade_date": ["2025-01-02", "2025-01-03"]}).to_parquet(
        root / "trading_calendar" / "trading_calendar.parquet",
        index=False,
    )
    (root / "instruments").mkdir(parents=True)
    pd.DataFrame({"order_book_id": ["000001.XSHE"], "listed_date": ["1991-04-03"]}).to_parquet(
        root / "instruments" / "instruments.parquet",
        index=False,
    )
    (root / "prices_1d_pre").mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-03"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "close": [10.0, 10.2],
        }
    ).to_parquet(root / "prices_1d_pre" / "year=2025.parquet", index=False)


if __name__ == "__main__":
    raise SystemExit(main())
