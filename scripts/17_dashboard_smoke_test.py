from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request


API_URL = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
PATHS = [
    "/ui",
    "/ui/backtests/current",
    "/ui/backtests/current/overview",
    "/ui/backtests/current/nav",
    "/ui/backtests/current/trades",
    "/ui/backtests/current/logs",
]


def main() -> int:
    try:
        for path in PATHS:
            status, length = _request(path)
            print(f"{path} {status} {length}")
    except urllib.error.URLError:
        print("API 未启动，请先运行：make api")
        return 1
    return 0


def _request(path: str) -> tuple[int, int]:
    request = urllib.request.Request(f"{API_URL}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        return response.status, len(body)


if __name__ == "__main__":
    raise SystemExit(main())
