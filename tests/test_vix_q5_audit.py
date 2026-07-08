from __future__ import annotations

import zipfile

import pandas as pd

from rq_platform.research.vix_q5_audit import (
    build_lagged_weights,
    build_weights_package,
    compare_summaries,
    compute_exposure_summary,
)


class FakeLoader:
    def load_valuation(self, symbols, start_date, end_date):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2025-01-02",
                    "order_book_id": "000001.XSHE",
                    "market_cap": 100.0,
                    "float_market_cap": 80.0,
                    "pe_ratio": 10.0,
                    "pb_ratio": 1.0,
                    "ps_ratio": 2.0,
                    "pcf_ratio": 3.0,
                    "turnover_rate": 0.01,
                },
                {
                    "trade_date": "2025-01-02",
                    "order_book_id": "600519.XSHG",
                    "market_cap": 300.0,
                    "float_market_cap": 240.0,
                    "pe_ratio": 20.0,
                    "pb_ratio": 2.0,
                    "ps_ratio": 4.0,
                    "pcf_ratio": 6.0,
                    "turnover_rate": 0.02,
                },
            ]
        )

    def load_industry(self, symbols, start_date, end_date):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2025-01-02",
                    "order_book_id": "000001.XSHE",
                    "industry_name": "Bank",
                },
                {
                    "trade_date": "2025-01-02",
                    "order_book_id": "600519.XSHG",
                    "industry_name": "Food",
                },
            ]
        )

    def load_index_components(self, index_ids, start_date, end_date):
        return pd.DataFrame(
            [
                {
                    "trade_date": "2025-01-02",
                    "index_id": "000300.XSHG",
                    "order_book_id": "000001.XSHE",
                }
            ]
        )


def test_build_lagged_weights_shifts_to_next_trading_date():
    weights = pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "order_book_id": "000001.XSHE", "target_weight": 1.0},
            {"trade_date": "2025-01-03", "order_book_id": "600519.XSHG", "target_weight": 1.0},
        ]
    )

    lagged = build_lagged_weights(weights, ["2025-01-02", "2025-01-03"])

    assert len(lagged) == 1
    assert lagged.iloc[0]["trade_date"] == "2025-01-03"
    assert lagged.iloc[0]["source_trade_date"] == "2025-01-02"


def test_compute_exposure_summary_with_fake_loader():
    weights = pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "order_book_id": "000001.XSHE", "target_weight": 0.25},
            {"trade_date": "2025-01-02", "order_book_id": "600519.XSHG", "target_weight": 0.75},
        ]
    )

    summary = compute_exposure_summary(weights, loader=FakeLoader())

    assert summary["unique_symbols"] == 2
    assert summary["valuation_weighted_average"]["market_cap"] == 250.0
    assert summary["index_overlap_average_weight"]["000300.XSHG"] == 0.25
    assert summary["top_industries_by_average_weight"][0]["industry_name"] == "Food"


def test_compare_summaries_calculates_difference():
    comparison = compare_summaries({"total_return": 0.10}, {"total_return": 0.07})

    row = comparison[comparison["metric"] == "total_return"].iloc[0]
    assert row["difference"] == -0.03


def test_build_weights_package_writes_standard_zip(tmp_path):
    config = {
        "package_version": "1.0",
        "strategy_id": "demo",
        "strategy_name": "Demo",
        "author": "tester",
        "description": "demo",
        "run": {
            "run_id": "demo_run",
            "start_date": "2025-01-02",
            "end_date": "2025-01-03",
            "initial_cash": 1000000,
            "benchmark": "000300.XSHG",
            "adjust_type": "pre",
            "frequency": "daily",
            "commission_rate": 0.0003,
            "tax_rate": 0.001,
            "slippage_rate": 0.0001,
            "lot_size": 100,
            "price_field": "close",
        },
    }
    weights = pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000001.XSHE",
                "target_weight": 1.0,
                "source_trade_date": "2025-01-01",
            }
        ]
    )

    output = build_weights_package(config, weights, tmp_path / "package.zip")

    with zipfile.ZipFile(output) as archive:
        assert sorted(archive.namelist()) == [
            "README.md",
            "config.json",
            "manifest.json",
            "weights.parquet",
        ]
