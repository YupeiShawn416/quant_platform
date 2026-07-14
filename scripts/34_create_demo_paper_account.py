from __future__ import annotations

import os
import sys

import requests


def main() -> int:
    base_url = os.getenv("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.getenv("QUANT_PLATFORM_API_TOKEN", "change_me")
    payload = {
        "paper_id": os.getenv("PAPER_ID", "demo_paper_account"),
        "strategy_name": os.getenv("STRATEGY_NAME", "demo_paper_strategy"),
        "initial_cash": float(os.getenv("INITIAL_CASH", "1000000")),
        "benchmark": os.getenv("BENCHMARK", "000300.XSHG"),
    }
    try:
        response = requests.post(
            f"{base_url}/paper/accounts",
            json=payload,
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
    account = data["account"]
    print(f"status={data['status']}")
    print(f"paper_id={account['paper_id']}")
    print(f"dashboard={base_url}/ui/paper/{account['paper_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
