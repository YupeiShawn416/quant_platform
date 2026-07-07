from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


URLS = [
    "/health",
    "/status",
    "/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume",
    "/data-quality?year=2025",
]


def main() -> None:
    base_url = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("QUANT_PLATFORM_API_TOKEN")
    for path in URLS:
        try:
            request = Request(f"{base_url}{path}", headers=_headers(token))
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                print(f"{path} status={response.status} {_summary(payload)}")
        except URLError:
            print("请先运行：make api")
            raise SystemExit(1)


def _headers(token: str | None) -> dict[str, str]:
    if token:
        return {"X-API-Token": token}
    return {}


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
