from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.factors.factor_metrics import (
    coverage_by_date,
    extreme_stats,
    forward_returns,
    group_nav,
    group_returns,
    ic_daily,
    ic_summary,
    top_quantile_turnover,
)
from rq_platform.factors.factor_registry import FactorRegistry
from rq_platform.factors.factor_store import FactorStore
from rq_platform.settings import settings


class FactorAnalyzer:
    def __init__(self, data_root: str | Path | None = None, store: FactorStore | None = None):
        self.data_root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
        self.store = store or FactorStore()
        self.registry = FactorRegistry()

    def analyze(
        self,
        factor_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
        groups: int = 5,
    ) -> dict[str, Any]:
        definition = self.registry.get(factor_id)
        values = self.store.read_values(factor_id, start_date, end_date)
        prices = self._read_prices(values["trade_date"].min(), values["trade_date"].max())
        fwd = forward_returns(prices)
        merged = values.merge(fwd, on=["trade_date", "order_book_id"], how="left")
        coverage = coverage_by_date(values)
        ic = ic_daily(merged)
        group_ret = group_returns(merged, groups=groups)
        nav = group_nav(group_ret)
        turnover = top_quantile_turnover(values)
        latest = str(values["trade_date"].max()) if not values.empty else None
        top_bottom = self.top_bottom_latest(values)
        summary = {
            "factor_id": factor_id,
            "name": definition.name,
            "category": definition.category,
            "latest_date": latest,
            "row_count": int(len(values)),
            "coverage_latest": _latest_value(coverage, "coverage_rate"),
            "missing_rate_latest": _latest_value(coverage, "missing_rate"),
            "extreme_stats": extreme_stats(values),
            "ic_summary": ic_summary(ic),
            "long_short_return": _long_short_return(nav),
            "turnover_latest": _latest_value(turnover, "turnover"),
        }
        files = {
            "factor_summary.json": summary,
            "factor_summary.md": self._summary_markdown(summary),
            "ic_daily.csv": ic,
            "group_returns.csv": group_ret,
            "group_nav.csv": nav,
            "turnover.csv": turnover,
            "coverage.csv": coverage,
            "top_bottom_latest.csv": top_bottom,
        }
        self.store.write_analysis(factor_id, files)
        return summary

    def top_bottom_latest(self, values: pd.DataFrame, n: int = 20) -> pd.DataFrame:
        if values.empty:
            return pd.DataFrame(columns=["side", "trade_date", "order_book_id", "factor_value", "factor_score"])
        latest = str(values["trade_date"].max())
        frame = values[values["trade_date"].astype(str) == latest].dropna(subset=["factor_score"])
        top = frame.nlargest(n, "factor_score").copy()
        bottom = frame.nsmallest(n, "factor_score").copy()
        top["side"] = "top"
        bottom["side"] = "bottom"
        return pd.concat([top, bottom], ignore_index=True)[["side", "trade_date", "order_book_id", "factor_value", "factor_score"]]

    def _read_prices(self, start_date: str, end_date: str) -> pd.DataFrame:
        root = self.data_root / "prices_1d_pre"
        years = range(int(start_date[:4]), int(end_date[:4]) + 1)
        files = [root / f"year={year}.parquet" for year in years if (root / f"year={year}.parquet").exists()]
        if not files:
            raise FileNotFoundError("prices_1d_pre dataset not found")
        frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        return frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)]

    def _summary_markdown(self, summary: dict[str, Any]) -> str:
        return (
            f"# {summary['name']}\n\n"
            f"- factor_id: {summary['factor_id']}\n"
            f"- category: {summary['category']}\n"
            f"- latest_date: {summary['latest_date']}\n"
            f"- rows: {summary['row_count']}\n"
            f"- IC mean: {summary['ic_summary'].get('ic_mean')}\n"
            f"- ICIR: {summary['ic_summary'].get('icir')}\n"
        )


def _latest_value(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    value = frame.sort_values("trade_date").iloc[-1][column]
    return None if pd.isna(value) else float(value)


def _long_short_return(nav: pd.DataFrame) -> float | None:
    if nav.empty:
        return None
    ls = nav[nav["group"].astype(str) == "long_short"].sort_values("trade_date")
    if ls.empty:
        return None
    return float(ls.iloc[-1]["nav"]) - 1.0

