from __future__ import annotations

import os

import requests

from rq_platform.client import QuantPlatformClient


def main() -> None:
    base_url = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000")
    token = os.environ.get("QUANT_PLATFORM_API_TOKEN")
    client = QuantPlatformClient(base_url=base_url, token=token)

    try:
        health = client.health()
        status = client.status()
        quality = client.data_quality(year=2025)
        prices = client.get_prices(
            symbols=["000001.XSHE", "600519.XSHG"],
            start="2025-01-02",
            end="2025-01-10",
            adjust_type="pre",
            fields=["open", "close", "volume"],
        )
    except requests.RequestException:
        print("请先运行：make api")
        raise SystemExit(1)

    datasets = status.get("datasets", {})
    datasets_ready = [name for name, item in datasets.items() if item.get("exists")]
    quality_rows = [item.get("rows", 0) for item in quality.get("results", [])]

    print(f"health status: {health.get('status')}")
    print(f"datasets_ready: {len(datasets_ready)}")
    print(f"data_quality rows: {quality_rows}")
    print(f"prices shape: {prices.shape}")
    print(prices.head())


if __name__ == "__main__":
    main()
