from __future__ import annotations

import pandas as pd


def build_equal_weight_portfolio(signal: pd.DataFrame, top_n: int) -> pd.DataFrame:
    required = {"trade_date", "order_book_id", "signal_score"}
    missing = required - set(signal.columns)
    if missing:
        raise ValueError(f"signal missing required columns: {sorted(missing)}")

    rows: list[dict[str, object]] = []
    frame = signal.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame = frame.dropna(subset=["signal_score"])

    for trade_date, daily in frame.groupby("trade_date"):
        selected = daily.sort_values("signal_score", ascending=False).head(top_n)
        if selected.empty:
            continue
        weight = 1.0 / len(selected)
        for order_book_id in selected["order_book_id"]:
            rows.append(
                {
                    "trade_date": trade_date.date().isoformat(),
                    "order_book_id": order_book_id,
                    "weight": weight,
                }
            )

    return pd.DataFrame(rows, columns=["trade_date", "order_book_id", "weight"])
