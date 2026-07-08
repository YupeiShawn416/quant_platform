from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


API_URL = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.environ.get("QUANT_PLATFORM_API_TOKEN")
ZIP_PATH = Path("/tmp/backtest_result_api_demo_backtest.zip")


def main() -> int:
    request_payload = {
        "strategy_code": (
            "def generate_weights(context, data):\n"
            "    return {'000001.XSHE': 0.5, '600519.XSHG': 0.5}\n"
        ),
        "config": {
            "run_id": "api_demo_backtest",
            "strategy_name": "api_demo",
            "start_date": "2025-01-02",
            "end_date": "2025-02-28",
            "initial_cash": 1000000,
            "benchmark": "000300.XSHG",
            "adjust_type": "pre",
            "frequency": "daily",
            "commission_rate": 0.0003,
            "tax_rate": 0.001,
            "slippage_rate": 0.0001,
            "lot_size": 100,
            "price_field": "close",
        },
    }
    try:
        run_result = _json_request("POST", "/backtests/run", request_payload)
        current = _json_request("GET", "/backtests/current")
        summary = _json_request("GET", "/backtests/current/summary")
        nav = _json_request("GET", "/backtests/current/nav")
        trades = _json_request("GET", "/backtests/current/trades")
        _download("/backtests/current/download", ZIP_PATH)
    except urllib.error.URLError:
        print("API 未启动，请先运行：make api")
        return 1

    print(f"run status: {run_result.get('status')}")
    print(f"current exists: {current.get('exists')}")
    print(f"total_return: {summary.get('total_return')}")
    print(f"sharpe: {summary.get('sharpe')}")
    print(f"max_drawdown: {summary.get('max_drawdown')}")
    print(f"nav count: {nav.get('count')}")
    print(f"trades count: {trades.get('count')}")
    print(f"zip path: {ZIP_PATH}")
    return 0 if run_result.get("status") == "success" else 1


def _headers() -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if API_TOKEN:
        headers["X-API-Token"] = API_TOKEN
    return headers


def _json_request(method: str, path: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=data,
        headers=_headers(),
        method=method,
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(path: str, target: Path) -> None:
    request = urllib.request.Request(f"{API_URL}{path}", headers=_headers(), method="GET")
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())


if __name__ == "__main__":
    raise SystemExit(main())
