from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.factors.factor_store import FactorStore
from rq_platform.settings import settings


class FactorWeightGenerator:
    def __init__(self, store: FactorStore | None = None, output_root: str | Path | None = None):
        self.store = store or FactorStore()
        self.output_root = Path(output_root).resolve() if output_root is not None else settings.factor_weights_dir_path

    def generate(
        self,
        factor_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        top_quantile: float = 0.2,
        max_names: int = 50,
        rebalance_frequency: str = "daily",
        weight_method: str = "equal",
    ) -> dict[str, Any]:
        if not 0 < top_quantile <= 1:
            raise ValueError("top_quantile must be between 0 and 1")
        if max_names < 1:
            raise ValueError("max_names must be >= 1")
        if rebalance_frequency not in {"daily", "weekly", "monthly"}:
            raise ValueError("rebalance_frequency must be daily, weekly, or monthly")
        if weight_method != "equal":
            raise ValueError("weight_method only supports equal in MVP")
        values = self.store.read_values(factor_id, start_date, end_date)
        weights = self._weights(values, top_quantile, max_names, rebalance_frequency)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_dir = self.output_root / f"{factor_id}_{timestamp}"
        output_dir.mkdir(parents=True, exist_ok=True)
        weights_path = output_dir / "target_weights.csv"
        manifest_path = output_dir / "manifest.json"
        readme_path = output_dir / "README.md"
        weights.to_csv(weights_path, index=False)
        manifest = {
            "factor_id": factor_id,
            "created_at": timestamp,
            "start_date": start_date,
            "end_date": end_date,
            "top_quantile": top_quantile,
            "max_names": max_names,
            "rebalance_frequency": rebalance_frequency,
            "weight_method": weight_method,
            "row_count": int(len(weights)),
            "target_weights_file": "target_weights.csv",
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        readme_path.write_text(
            "# Factor Weights\n\n"
            f"- factor_id: {factor_id}\n"
            f"- rows: {len(weights)}\n"
            "- This file is long-only and can be used for weights package or paper trading.\n",
            encoding="utf-8",
        )
        return {
            "factor_id": factor_id,
            "row_count": int(len(weights)),
            "output_dir": str(output_dir),
            "target_weights": str(weights_path),
            "manifest": str(manifest_path),
        }

    def _weights(
        self,
        values: pd.DataFrame,
        top_quantile: float,
        max_names: int,
        rebalance_frequency: str,
    ) -> pd.DataFrame:
        dates = _rebalance_dates(sorted(values["trade_date"].astype(str).unique()), rebalance_frequency)
        rows = []
        for trade_date in dates:
            part = values[(values["trade_date"].astype(str) == trade_date) & values["factor_score"].notna()]
            if part.empty:
                continue
            count = min(max_names, max(1, int(len(part) * top_quantile)))
            selected = part.nlargest(count, "factor_score")
            weight = 1.0 / len(selected)
            for symbol in selected["order_book_id"].astype(str):
                rows.append({"trade_date": trade_date, "order_book_id": symbol, "target_weight": weight})
        return pd.DataFrame(rows, columns=["trade_date", "order_book_id", "target_weight"])


def _rebalance_dates(dates: list[str], frequency: str) -> list[str]:
    if frequency == "daily":
        return dates
    frame = pd.DataFrame({"trade_date": pd.to_datetime(dates)})
    if frequency == "weekly":
        return frame.groupby(frame["trade_date"].dt.to_period("W"))["trade_date"].first().dt.strftime("%Y-%m-%d").tolist()
    return frame.groupby(frame["trade_date"].dt.to_period("M"))["trade_date"].first().dt.strftime("%Y-%m-%d").tolist()

