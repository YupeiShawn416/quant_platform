from __future__ import annotations

from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from rq_platform.factors.factor_cleaning import clean_factor_values
from rq_platform.factors.factor_registry import FactorRegistry
from rq_platform.factors.factor_store import FactorStore
from rq_platform.settings import settings


INDEX_UNIVERSES = {"csi300": "000300.XSHG", "csi500": "000905.XSHG", "csi800": "000906.XSHG"}


class FactorCalculator:
    def __init__(self, data_root: str | Path | None = None, store: FactorStore | None = None):
        self.data_root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
        self.store = store or FactorStore()
        self.registry = FactorRegistry(self.store.root / "registry" / "factor_registry.json")

    def compute(
        self,
        factor_ids: Iterable[str],
        start_date: str,
        end_date: str,
        universe: str = "all",
        overwrite: bool = True,
    ) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for factor_id in factor_ids:
            frame = self.compute_factor(factor_id, start_date, end_date, universe)
            paths = self.store.write_values(factor_id, frame, overwrite=overwrite)
            results[factor_id] = {"rows": int(len(frame)), "paths": [str(path) for path in paths]}
        self.registry.write_registry()
        return results

    def compute_factor(self, factor_id: str, start_date: str, end_date: str, universe: str = "all") -> pd.DataFrame:
        self.registry.get(factor_id)
        if factor_id in {"market_cap", "turnover_rate"}:
            frame = self._valuation_factor(factor_id, start_date, end_date)
        elif factor_id in {"momentum_20d", "reversal_5d", "volatility_20d"}:
            frame = self._price_factor(factor_id, start_date, end_date)
        else:
            raise ValueError(f"unsupported factor_id: {factor_id}")
        frame = self._filter_universe(frame, universe, start_date, end_date)
        frame = frame.drop_duplicates(["trade_date", "order_book_id"]).sort_values(["trade_date", "order_book_id"])
        return clean_factor_values(frame).reset_index(drop=True)

    def _valuation_factor(self, factor_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        frame = self._read_partitioned("valuation_1d", start_date, end_date)
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        if factor_id == "market_cap":
            column = _first_existing(frame, ["market_cap", "total_market_cap", "circulating_market_cap"])
            value = pd.to_numeric(frame[column], errors="coerce")
            factor_value = -np.log(value.where(value > 0))
        else:
            column = _first_existing(frame, ["turnover_rate", "turnover_ratio"])
            factor_value = -pd.to_numeric(frame[column], errors="coerce")
        return pd.DataFrame(
            {
                "trade_date": frame["trade_date"],
                "order_book_id": frame["order_book_id"].astype(str),
                "factor_value": factor_value,
            }
        )

    def _price_factor(self, factor_id: str, start_date: str, end_date: str) -> pd.DataFrame:
        lookback = 25
        warm_start = (pd.Timestamp(start_date) - pd.Timedelta(days=lookback * 2)).strftime("%Y-%m-%d")
        prices = self._read_partitioned("prices_1d_pre", warm_start, end_date)
        prices["trade_date"] = pd.to_datetime(prices["trade_date"]).dt.strftime("%Y-%m-%d")
        prices = prices.sort_values(["order_book_id", "trade_date"])
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        grouped = prices.groupby("order_book_id")["close"]
        if factor_id == "momentum_20d":
            values = grouped.transform(lambda s: s / s.shift(20) - 1.0)
        elif factor_id == "reversal_5d":
            values = -grouped.transform(lambda s: s / s.shift(5) - 1.0)
        else:
            returns = grouped.pct_change()
            values = returns.groupby(prices["order_book_id"]).transform(lambda s: s.rolling(20, min_periods=20).std())
            values = -values
        output = pd.DataFrame(
            {
                "trade_date": prices["trade_date"],
                "order_book_id": prices["order_book_id"].astype(str),
                "factor_value": values,
            }
        )
        return output[(output["trade_date"] >= start_date) & (output["trade_date"] <= end_date)]

    def _filter_universe(self, frame: pd.DataFrame, universe: str, start_date: str, end_date: str) -> pd.DataFrame:
        if universe == "all":
            return frame
        if universe not in INDEX_UNIVERSES:
            raise ValueError(f"unsupported universe: {universe}")
        try:
            components = self._read_partitioned("index_components", start_date, end_date)
        except FileNotFoundError:
            return frame.iloc[0:0].copy()
        index_id = INDEX_UNIVERSES[universe]
        components["trade_date"] = pd.to_datetime(components["trade_date"]).dt.strftime("%Y-%m-%d")
        components = components[components["index_id"].astype(str) == index_id]
        pairs = components[["trade_date", "order_book_id"]].drop_duplicates()
        return frame.merge(pairs, on=["trade_date", "order_book_id"], how="inner")

    def _read_partitioned(self, dataset: str, start_date: str, end_date: str) -> pd.DataFrame:
        root = self.data_root / dataset
        years = range(int(start_date[:4]), int(end_date[:4]) + 1)
        files = [root / f"year={year}.parquet" for year in years if (root / f"year={year}.parquet").exists()]
        if not files:
            raise FileNotFoundError(f"dataset not found: {dataset}")
        frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        return frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)].reset_index(drop=True)


def _first_existing(frame: pd.DataFrame, candidates: list[str]) -> str:
    for column in candidates:
        if column in frame.columns:
            return column
    raise ValueError(f"missing required columns, expected one of: {', '.join(candidates)}")
