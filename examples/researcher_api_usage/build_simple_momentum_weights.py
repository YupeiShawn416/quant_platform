from __future__ import annotations

from pathlib import Path

import pandas as pd


OUTPUT_DIR = Path(__file__).resolve().parent / "output"
PRICE_PATH = OUTPUT_DIR / "prices_sample.csv"
WEIGHTS_PATH = OUTPUT_DIR / "simple_momentum_weights.csv"


def main() -> int:
    if not PRICE_PATH.exists():
        print(f"Missing input: {PRICE_PATH}")
        print("Run fetch_prices_example.py first while the platform API is online.")
        return 1

    prices = pd.read_csv(PRICE_PATH)
    required = {"trade_date", "order_book_id", "close"}
    missing = required - set(prices.columns)
    if missing:
        print(f"prices_sample.csv missing columns: {sorted(missing)}")
        return 1

    frame = prices.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    frame = frame.sort_values(["order_book_id", "trade_date"])
    frame["momentum"] = frame.groupby("order_book_id")["close"].pct_change(5)
    rows = []
    for trade_date, group in frame.dropna(subset=["momentum"]).groupby("trade_date"):
        selected = group.sort_values(["momentum", "order_book_id"], ascending=[False, True]).head(1)
        for _, row in selected.iterrows():
            rows.append(
                {
                    "trade_date": trade_date.strftime("%Y-%m-%d"),
                    "order_book_id": row["order_book_id"],
                    "target_weight": 1.0,
                    "signal_score": row["momentum"],
                }
            )

    weights = pd.DataFrame(rows)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    weights.to_csv(WEIGHTS_PATH, index=False)
    print(f"rows={len(weights)}")
    print(f"output={WEIGHTS_PATH}")
    print("Teaching example only. Use research_weights_template for real packages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
