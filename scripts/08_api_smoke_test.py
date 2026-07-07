from __future__ import annotations

import json
from urllib.error import URLError
from urllib.request import urlopen


BASE_URL = "http://127.0.0.1:8000"
URLS = [
    "/health",
    "/status",
    "/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume",
    "/data-quality?year=2025",
]


def main() -> None:
    for path in URLS:
        try:
            with urlopen(f"{BASE_URL}{path}", timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                print(f"{path} status={response.status} {_summary(payload)}")
        except URLError:
            print("请先运行：PYTHONPATH=src python scripts/07_run_api_local.py")
            raise SystemExit(1)


def _summary(payload: dict) -> str:
    if "count" in payload:
        return f"count={payload['count']}"
    if "status" in payload:
        return f"status={payload['status']}"
    if "datasets" in payload:
        datasets = payload["datasets"]
        ready = [name for name, item in datasets.items() if item.get("exists")]
        return f"datasets_ready={len(ready)}"
    if "results" in payload:
        rows = [item.get("rows", 0) for item in payload["results"]]
        return f"results={len(payload['results'])} rows={rows}"
    return "ok"


if __name__ == "__main__":
    main()
