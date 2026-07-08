from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path


API_URL = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.environ.get("QUANT_PLATFORM_API_TOKEN")
PACKAGE_ZIP = Path("/tmp/demo_weights_strategy_package.zip")
RESULT_ZIP = Path("/tmp/backtest_result_demo_weights_package.zip")


def main() -> int:
    if not PACKAGE_ZIP.exists():
        print("demo package 不存在，请先运行：make create-demo-weights-package")
        return 1
    try:
        result = _upload_package()
        summary = _json_request("GET", "/backtests/current/summary")
        nav = _json_request("GET", "/backtests/current/nav")
        trades = _json_request("GET", "/backtests/current/trades")
        _download("/backtests/current/download", RESULT_ZIP)
    except urllib.error.URLError:
        print("API 未启动，请先运行：make api")
        return 1
    print(f"run status: {result.get('status')}")
    print(f"total_return: {summary.get('total_return')}")
    print(f"sharpe: {summary.get('sharpe')}")
    print(f"max_drawdown: {summary.get('max_drawdown')}")
    print(f"nav count: {nav.get('count')}")
    print(f"trades count: {trades.get('count')}")
    print(f"result zip: {RESULT_ZIP}")
    return 0 if result.get("status") == "success" else 1


def _headers(content_type: str | None = None) -> dict[str, str]:
    headers = {}
    if content_type:
        headers["Content-Type"] = content_type
    if API_TOKEN:
        headers["X-API-Token"] = API_TOKEN
    return headers


def _upload_package() -> dict:
    boundary = "----quant-platform-boundary"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="demo_weights_strategy_package.zip"\r\n',
            b"Content-Type: application/zip\r\n\r\n",
            PACKAGE_ZIP.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    request = urllib.request.Request(
        f"{API_URL}/backtests/run-package",
        data=body,
        headers=_headers(f"multipart/form-data; boundary={boundary}"),
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def _json_request(method: str, path: str) -> dict:
    request = urllib.request.Request(f"{API_URL}{path}", headers=_headers(), method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _download(path: str, target: Path) -> None:
    request = urllib.request.Request(f"{API_URL}{path}", headers=_headers(), method="GET")
    with urllib.request.urlopen(request, timeout=120) as response:
        target.write_bytes(response.read())


if __name__ == "__main__":
    raise SystemExit(main())
