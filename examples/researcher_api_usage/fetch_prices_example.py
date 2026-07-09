from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import requests


BASE_URL = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000").rstrip("/")
TOKEN = os.environ.get("QUANT_PLATFORM_API_TOKEN")
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def main() -> int:
    headers = {"X-API-Token": TOKEN} if TOKEN else {}
    try:
        status = requests.get(f"{BASE_URL}/status", headers=headers, timeout=10)
        status.raise_for_status()
        response = requests.get(
            f"{BASE_URL}/prices",
            params={
                "symbols": "000001.XSHE,600519.XSHG",
                "start": "2025-01-02",
                "end": "2025-01-31",
                "adjust_type": "pre",
                "fields": "open,close,volume",
            },
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"API request failed: {exc}")
        print("Start the API first, for example: make api")
        return 1

    payload = response.json()
    frame = pd.DataFrame(payload.get("data", []))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "prices_sample.csv"
    frame.to_csv(output_path, index=False)
    print(f"rows={len(frame)}")
    print(f"output={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
