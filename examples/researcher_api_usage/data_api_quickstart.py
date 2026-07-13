from __future__ import annotations

import os

import pandas as pd

from quant_platform_client import QuantPlatformClient


BASE_URL = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000")
API_TOKEN = os.environ.get("QUANT_PLATFORM_API_TOKEN")


def main() -> int:
    client = QuantPlatformClient(BASE_URL, API_TOKEN)

    calendar = client.get_trading_calendar("2025-01-02", "2025-01-31")
    prices = client.get_prices(
        "2025-01-02",
        "2025-01-31",
        order_book_ids=["000001.XSHE", "600519.XSHG"],
        fields=["trade_date", "order_book_id", "close", "volume"],
    )
    valuation = client.get_valuation(
        "2025-01-02",
        "2025-01-31",
        order_book_ids=["000001.XSHE", "600519.XSHG"],
        fields=["trade_date", "order_book_id", "pe_ratio", "pb_ratio"],
    )

    panel = prices.merge(valuation, on=["trade_date", "order_book_id"], how="left")
    latest_date = panel["trade_date"].max() if not panel.empty else None
    weights = _equal_weight_panel(panel, latest_date)

    print(f"calendar rows={len(calendar)}")
    print(f"prices rows={len(prices)}")
    print(f"valuation rows={len(valuation)}")
    print(f"feature panel rows={len(panel)}")
    print(weights)
    return 0


def _equal_weight_panel(panel: pd.DataFrame, trade_date: str | None) -> pd.DataFrame:
    if panel.empty or trade_date is None:
        return pd.DataFrame(columns=["trade_date", "order_book_id", "weight"])
    symbols = sorted(panel.loc[panel["trade_date"] == trade_date, "order_book_id"].dropna().unique())
    if not symbols:
        return pd.DataFrame(columns=["trade_date", "order_book_id", "weight"])
    weight = 1.0 / len(symbols)
    return pd.DataFrame(
        {"trade_date": [trade_date] * len(symbols), "order_book_id": symbols, "weight": [weight] * len(symbols)}
    )


if __name__ == "__main__":
    raise SystemExit(main())
