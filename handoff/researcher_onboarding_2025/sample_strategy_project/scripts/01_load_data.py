from __future__ import annotations

import os
import sys

import pandas as pd
import requests

from common import load_config, project_path


def main() -> int:
    config = load_config()
    api_url = os.getenv("QUANT_PLATFORM_API_URL", "<SERVER_URL>").rstrip("/")
    api_token = os.getenv("QUANT_PLATFORM_API_TOKEN", "")

    if api_url == "<SERVER_URL>" or not api_token:
        print("请先设置 QUANT_PLATFORM_API_URL 和 QUANT_PLATFORM_API_TOKEN。")
        return 1

    run = config["run"]
    symbols = config["universe"]["symbols"]
    params = {
        "symbols": ",".join(symbols),
        "start": run["start_date"],
        "end": run["end_date"],
        "fields": "close,volume",
        "adjust_type": run["adjust_type"],
    }
    headers = {"X-API-Token": api_token}

    try:
        response = requests.get(f"{api_url}/prices", params=params, headers=headers, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"读取行情失败：{exc}")
        print("请确认 QUANT_PLATFORM_API_URL/QUANT_PLATFORM_API_TOKEN/API 可用。")
        return 1

    payload = response.json()
    data = payload.get("data", payload)
    prices = pd.DataFrame(data)
    if prices.empty:
        print("平台返回空行情，请检查 universe 和日期范围。")
        return 1

    output_path = project_path(config["output"]["price_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prices.to_csv(output_path, index=False)
    print(f"saved prices: {output_path} rows={len(prices)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
