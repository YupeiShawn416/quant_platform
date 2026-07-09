from __future__ import annotations

import os
import sys

import requests

from common import load_config, project_path


def main() -> int:
    config = load_config()
    api_url = os.getenv("QUANT_PLATFORM_API_URL", "<SERVER_URL>").rstrip("/")
    api_token = os.getenv("QUANT_PLATFORM_API_TOKEN", "")

    if api_url == "<SERVER_URL>" or not api_token:
        print("请先设置 QUANT_PLATFORM_API_URL 和 QUANT_PLATFORM_API_TOKEN。")
        return 1

    package_path = project_path(config["output"]["package_path"])
    if not package_path.exists():
        print("找不到 strategy_package.zip，请先运行 scripts/06_build_package.py。")
        return 1

    headers = {"X-API-Token": api_token}
    try:
        with package_path.open("rb") as file:
            response = requests.post(
                f"{api_url}/backtests/run-package",
                headers=headers,
                files={"file": ("strategy_package.zip", file, "application/zip")},
                timeout=120,
            )
        response.raise_for_status()
        run_payload = response.json()

        summary_response = requests.get(
            f"{api_url}/backtests/current/summary", headers=headers, timeout=30
        )
        summary_response.raise_for_status()
        summary = summary_response.json()

        download_response = requests.get(
            f"{api_url}/backtests/current/download", headers=headers, timeout=60
        )
        download_response.raise_for_status()
    except requests.RequestException as exc:
        print(f"提交或下载失败：{exc}")
        print("请确认 QUANT_PLATFORM_API_URL/QUANT_PLATFORM_API_TOKEN/API 可用。")
        return 1

    result_zip_path = project_path(config["output"]["result_zip_path"])
    result_zip_path.parent.mkdir(parents=True, exist_ok=True)
    result_zip_path.write_bytes(download_response.content)

    print(f"run status: {run_payload.get('status')}")
    print(f"run id: {summary.get('run_id')}")
    print(f"total_return: {summary.get('total_return')}")
    print(f"sharpe: {summary.get('sharpe')}")
    print(f"max_drawdown: {summary.get('max_drawdown')}")
    print(f"result zip: {result_zip_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
