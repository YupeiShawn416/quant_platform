from __future__ import annotations

import pandas as pd


class WeightFileStrategy:
    def __init__(self, weights_df: pd.DataFrame, weight_mode: str = "daily_target"):
        if weight_mode not in {"daily_target", "rebalance_only"}:
            raise ValueError("weight_mode must be daily_target or rebalance_only")
        self.weight_mode = weight_mode
        frame = weights_df.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame["target_weight"] = pd.to_numeric(frame["target_weight"], errors="coerce")
        frame = frame.dropna(subset=["target_weight"])
        frame = frame[frame["target_weight"] > 0]
        self.weights_by_date = {
            trade_date: group.set_index("order_book_id")["target_weight"].astype(float).to_dict()
            for trade_date, group in frame.groupby("trade_date")
        }

    def generate_weights(self, context, data) -> dict[str, float] | None:
        trade_date = str(context.current_date)
        weights = self.weights_by_date.get(trade_date)
        if weights is not None:
            return weights
        if self.weight_mode == "rebalance_only":
            return None
        return {}
