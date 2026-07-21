import pandas as pd
import importlib.util
import sys

from rq_platform.research.data_availability_probe import (
    build_research_report_data_availability,
    classify_probe_exception,
    is_rqdata_probe_enabled,
)
from rq_platform.research.report_data_requirements import FieldRequirement


def test_default_rqdata_probe_disabled():
    assert is_rqdata_probe_enabled({}) is False
    assert is_rqdata_probe_enabled({"ENABLE_RQDATA_PROBE": "0"}) is False
    assert is_rqdata_probe_enabled({"ENABLE_RQDATA_PROBE": "1"}) is True


def test_local_schema_available_missing_and_derived(tmp_path):
    prices = tmp_path / "prices_1d_none" / "year=2026"
    prices.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2026-07-10", "2026-07-11"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "close": [10.0, 10.2],
            "volume": [1000, 1200],
            "total_turnover": [10000.0, 12240.0],
        }
    ).to_parquet(prices / "part.parquet", index=False)

    requirements = [
        FieldRequirement("P0", "daily_market_core", "close", "收盘价", "raw", "daily", "daily", "test", "usage"),
        FieldRequirement("P0", "daily_market_core", "vwap", "成交均价", "raw", "daily", "daily", "test", "usage"),
        FieldRequirement("P0", "daily_market_core", "missing_raw", "缺失", "raw", "daily", "daily", "test", "usage"),
        FieldRequirement(
            "P0",
            "monthly_research_panel",
            "monthly_return",
            "月收益",
            "derived",
            "monthly",
            "monthly",
            "test",
            "usage",
            "close ratio",
            ("close",),
        ),
    ]

    result = build_research_report_data_availability(
        data_root=tmp_path,
        enable_rqdata_probe=False,
        requirements=requirements,
    )
    raw_by_field = {row["canonical_field"]: row for row in result["raw_availability"]}
    derived_by_field = {row["derived_field"]: row for row in result["derived_dependency"]}

    assert raw_by_field["close"]["local_status"] == "available"
    assert raw_by_field["close"]["local_row_count"] == 2
    assert raw_by_field["vwap"]["local_status"] == "derivable_from_existing"
    assert raw_by_field["missing_raw"]["local_status"] == "missing"
    assert derived_by_field["monthly_return"]["current_raw_field_status"] == "derivable_from_existing"
    assert result["rqdata_probe_enabled"] is False


def test_existing_partition_latest_not_usable(tmp_path):
    valuation = tmp_path / "valuation_1d" / "year=2026"
    valuation.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2026-07-10", "2026-07-11"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "market_cap": [100.0, None],
        }
    ).to_parquet(valuation / "part.parquet", index=False)
    requirements = [
        FieldRequirement("P0", "valuation_core", "market_cap", "总市值", "raw", "daily", "daily", "test", "usage"),
    ]

    result = build_research_report_data_availability(tmp_path, False, requirements)

    assert result["raw_availability"][0]["local_status"] == "available_but_latest_not_usable"


def test_permission_error_records_permission_required():
    assert classify_probe_exception(RuntimeError("Permission denied for factor")) == "permission_required"
    assert classify_probe_exception(RuntimeError("daily quota limit exceeded")) == "quota_limited"


def test_script_import_does_not_require_rqdatac(monkeypatch):
    monkeypatch.setitem(sys.modules, "rqdatac", None)
    spec = importlib.util.spec_from_file_location(
        "probe_research_report_data_availability",
        "scripts/46_probe_research_report_data_availability.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)

    spec.loader.exec_module(module)

    assert hasattr(module, "main")
