from __future__ import annotations

import pandas as pd


def generate_weights(signal_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    top_n = int(config.get("portfolio", {}).get("top_n", 4))
    if top_n <= 0:
        raise ValueError("portfolio.top_n must be positive")
    frame = signal_df.copy()
    frame["signal_score"] = pd.to_numeric(frame["signal_score"], errors="coerce").fillna(float("-inf"))
    rows = []
    for trade_date, group in frame.groupby("trade_date", sort=True):
        selected = group.sort_values(["signal_score", "order_book_id"], ascending=[False, True]).head(top_n)
        if selected.empty:
            continue
        weight = 1.0 / len(selected)
        for _, row in selected.iterrows():
            rows.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": row["order_book_id"],
                    "target_weight": weight,
                    "signal_score": row["signal_score"],
                }
            )
    return pd.DataFrame(rows)
