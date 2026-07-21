import json

import pandas as pd

from rq_platform.research.data_availability_report import (
    BACKFILL_PLAN_COLUMNS,
    DERIVED_DEPENDENCY_COLUMNS,
    RAW_AVAILABILITY_COLUMNS,
    build_backfill_plan,
    write_research_report_availability_outputs,
)


def _sample_result():
    return {
        "generated_at": "2026-07-21T00:00:00+08:00",
        "data_root": "/tmp/data",
        "rqdata_probe_enabled": False,
        "raw_availability": [
            {
                "priority": "P0",
                "data_pack": "daily_market_core",
                "canonical_field": "close",
                "chinese_name": "收盘价",
                "field_type": "raw",
                "required_frequency": "daily",
                "recommended_storage_frequency": "daily",
                "local_status": "available",
                "local_dataset": "prices_1d_none",
                "local_field": "close",
                "local_row_count": 2,
                "local_symbol_count": 1,
                "local_non_null_ratio": 1.0,
                "local_latest_non_null_date": "2026-07-11",
                "local_date_range": "2026-07-10 to 2026-07-11",
                "rqdata_probe_enabled": False,
                "rqdata_status": "not_probed",
                "rqdata_candidate_function": "get_price",
                "rqdata_candidate_field": "close",
                "rqdata_sample_rows": 0,
                "rqdata_error": "",
                "recommended_dataset_name": "prices_1d_none",
                "backfill_priority": "P0",
                "notes": "",
            },
            {
                "priority": "P1",
                "data_pack": "capital_flow_northbound_margin",
                "canonical_field": "northbound_net_buy_amount",
                "chinese_name": "northbound_net_buy_amount",
                "field_type": "raw",
                "required_frequency": "daily",
                "recommended_storage_frequency": "daily",
                "local_status": "missing",
                "local_dataset": "",
                "local_field": "",
                "local_row_count": 0,
                "local_symbol_count": None,
                "local_non_null_ratio": None,
                "local_latest_non_null_date": "",
                "local_date_range": "",
                "rqdata_probe_enabled": False,
                "rqdata_status": "not_probed",
                "rqdata_candidate_function": "capital_flow",
                "rqdata_candidate_field": "northbound_net_buy_amount",
                "rqdata_sample_rows": 0,
                "rqdata_error": "",
                "recommended_dataset_name": "capital_flow_1d",
                "backfill_priority": "P1",
                "notes": "",
            },
        ],
        "derived_dependency": [
            {
                "priority": "P0",
                "data_pack": "monthly_research_panel",
                "derived_field": "monthly_return",
                "chinese_name": "月收益",
                "required_frequency": "monthly",
                "formula": "close ratio",
                "required_raw_fields": "close",
                "current_raw_field_status": "derivable_from_existing",
                "missing_raw_fields": "",
                "recommended_materialization": "monthly",
                "notes": "",
            },
            {
                "priority": "P1",
                "data_pack": "capital_flow_northbound_margin",
                "derived_field": "retail_oib",
                "chinese_name": "散户订单不平衡",
                "required_frequency": "monthly",
                "formula": "small_order_net_inflow / total_turnover",
                "required_raw_fields": "small_order_net_inflow,total_turnover",
                "current_raw_field_status": "blocked_missing_raw",
                "missing_raw_fields": "small_order_net_inflow",
                "recommended_materialization": "derived",
                "notes": "",
            },
        ],
    }


def test_output_fields_complete_and_files_written(tmp_path):
    paths = write_research_report_availability_outputs(_sample_result(), tmp_path)

    raw = pd.read_csv(paths["raw_csv"])
    derived = pd.read_csv(paths["derived_csv"])
    plan = pd.read_csv(tmp_path / "research_report_data_backfill_plan.csv")

    assert list(raw.columns) == RAW_AVAILABILITY_COLUMNS
    assert list(derived.columns) == DERIVED_DEPENDENCY_COLUMNS
    assert list(plan.columns) == BACKFILL_PLAN_COLUMNS
    assert json.loads(paths["plan_json"].read_text(encoding="utf-8"))
    assert paths["raw_md"].read_text(encoding="utf-8").startswith("# Research Report Raw Data Availability")


def test_backfill_plan_aggregates_by_data_pack():
    plan = build_backfill_plan(
        _sample_result()["raw_availability"],
        _sample_result()["derived_dependency"],
    )
    by_pack = {row["data_pack"]: row for row in plan}

    assert "capital_flow_northbound_margin" in by_pack
    assert "northbound_net_buy_amount" in by_pack["capital_flow_northbound_margin"]["missing_raw_fields"]
    assert "retail_oib" in by_pack["capital_flow_northbound_margin"]["derived_blocked_fields"]
