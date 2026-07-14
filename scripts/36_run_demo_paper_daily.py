from __future__ import annotations

import os
import sys

import requests


def main() -> int:
    base_url = os.getenv("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.getenv("QUANT_PLATFORM_API_TOKEN", "change_me")
    paper_id = os.getenv("PAPER_ID", "demo_paper_account")
    trade_date = os.getenv("TRADE_DATE", "2026-07-10")
    try:
        response = requests.post(
            f"{base_url}/paper/accounts/{paper_id}/run-daily",
            json={"trade_date": trade_date},
            headers={"X-API-Token": token},
            timeout=60,
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
    print(f"trade_date={data['trade_date']}")
    print(f"nav={data['nav']:.6f}")
    print(f"orders={data['orders']}")
    print(f"trades={data['trades']}")
    print(f"dashboard={base_url}/ui/paper/{paper_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
