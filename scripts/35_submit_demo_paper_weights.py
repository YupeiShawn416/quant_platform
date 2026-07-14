from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import requests


def main() -> int:
    base_url = os.getenv("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.getenv("QUANT_PLATFORM_API_TOKEN", "change_me")
    paper_id = os.getenv("PAPER_ID", "demo_paper_account")
    trade_date = os.getenv("TRADE_DATE", "2026-07-10")
    path = Path("/tmp/demo_paper_target_weights.csv")
    pd.DataFrame(
        [
            {"trade_date": trade_date, "order_book_id": "000001.XSHE", "target_weight": 0.5},
            {"trade_date": trade_date, "order_book_id": "600519.XSHG", "target_weight": 0.3},
        ]
    ).to_csv(path, index=False)
    try:
        with path.open("rb") as file:
            response = requests.post(
                f"{base_url}/paper/accounts/{paper_id}/target-weights",
                files={"file": (path.name, file, "text/csv")},
                headers={"X-API-Token": token},
                timeout=30,
            )
    except requests.RequestException:
        print("请先运行：make api")
        return 2
    if response.status_code >= 400:
        print(response.text)
        return 1
    data = response.json()
    print(f"status={data['status']}")
    print(f"paper_id={data['paper_id']}")
    print(f"rows={data['rows']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
