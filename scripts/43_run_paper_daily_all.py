from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import requests


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all active paper accounts for one trade date.")
    parser.add_argument("--trade-date", default=os.getenv("TRADE_DATE"))
    parser.add_argument("--api-url", default=os.getenv("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    if not args.trade_date:
        print("TRADE_DATE or --trade-date is required, e.g. 2026-07-14")
        return 2

    token = os.getenv("QUANT_PLATFORM_API_TOKEN", "change_me")
    base_url = args.api_url.rstrip("/")
    try:
        response = requests.post(
            f"{base_url}/paper/run-daily-all",
            json={"trade_date": args.trade_date, "active_only": True},
            headers={"X-API-Token": token},
            timeout=args.timeout,
        )
    except requests.RequestException as exc:
        print(f"paper_run_daily_all_failed=request_error:{type(exc).__name__}")
        return 2

    if response.status_code >= 400:
        print(f"paper_run_daily_all_failed=http_{response.status_code}")
        print(response.text)
        return 1

    data: dict[str, Any] = response.json()
    results = data.get("results") or []
    failed = [item for item in results if item.get("status") != "success"]

    print(f"trade_date={data.get('trade_date')}")
    print(f"paper_account_count={data.get('count')}")
    print(f"failed_count={len(failed)}")
    for item in results:
        paper_id = item.get("paper_id")
        status = item.get("status")
        nav = item.get("nav", "")
        orders = item.get("orders", "")
        trades = item.get("trades", "")
        error = item.get("error", "")
        print(
            f"paper_id={paper_id} status={status} nav={nav} "
            f"orders={orders} trades={trades} error={error}"
        )
    print(f"dashboard={base_url}/ui/paper")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
