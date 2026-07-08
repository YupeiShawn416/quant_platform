from pathlib import Path
import json
import os
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config


API_URL = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
API_TOKEN = os.environ.get("QUANT_PLATFORM_API_TOKEN")
RESULT_ZIP = Path("/tmp/backtest_result_demo_weights_template.zip")


def headers(content_type=None):
    values = {}
    if content_type:
        values["Content-Type"] = content_type
    if API_TOKEN:
        values["X-API-Token"] = API_TOKEN
    return values


def request_json(method, path):
    request = urllib.request.Request(f"{API_URL}{path}", headers=headers(), method=method)
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    config = load_config()
    package_path = Path(config["output"]["package_path"])
    if not package_path.exists():
        print("strategy package 不存在，请先运行：python scripts/06_build_package.py")
        return 1
    boundary = "----strategy-template-boundary"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="file"; filename="strategy_package.zip"\r\n',
            b"Content-Type: application/zip\r\n\r\n",
            package_path.read_bytes(),
            f"\r\n--{boundary}--\r\n".encode(),
        ]
    )
    try:
        upload = urllib.request.Request(
            f"{API_URL}/backtests/run-package",
            data=body,
            headers=headers(f"multipart/form-data; boundary={boundary}"),
            method="POST",
        )
        with urllib.request.urlopen(upload, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
        current = request_json("GET", "/backtests/current")
        summary = request_json("GET", "/backtests/current/summary")
        download = urllib.request.Request(f"{API_URL}/backtests/current/download", headers=headers(), method="GET")
        with urllib.request.urlopen(download, timeout=120) as response:
            RESULT_ZIP.write_bytes(response.read())
    except urllib.error.URLError:
        print("请先在 quant_platform 中运行 make api")
        return 1
    print(f"run status: {result.get('status')}")
    print(f"current exists: {current.get('exists')}")
    print(f"total_return: {summary.get('total_return')}")
    print(f"result zip: {RESULT_ZIP}")
    return 0 if result.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
