from __future__ import annotations

import pandas as pd
import pytest

from rq_platform.research.rqdata_field_probe import (
    P0_PROBE_COLUMNS,
    RQDataFieldProbe,
    build_after_probe_plan,
    load_p0_probe_inputs,
    sanitize_error_message,
)


def _raw_csv(path):
    rows = [
        {
            "priority": "P0",
            "data_pack": "valuation_core",
            "canonical_field": "pe_ttm",
            "chinese_name": "滚动市盈率",
            "field_type": "raw",
            "required_frequency": "daily",
            "local_status": "missing",
            "rqdata_candidate_function": "get_factor",
            "rqdata_candidate_field": "pe_ttm",
            "recommended_dataset_name": "valuation_1d",
            "notes": "",
        },
        {
            "priority": "P0",
            "data_pack": "monthly_research_panel",
            "canonical_field": "monthly_return",
            "chinese_name": "月收益",
            "field_type": "derived",
            "required_frequency": "monthly",
            "local_status": "missing",
            "rqdata_candidate_function": "",
            "rqdata_candidate_field": "",
            "recommended_dataset_name": "derived",
            "notes": "",
        },
        {
            "priority": "P1",
            "data_pack": "capital_flow_northbound_margin",
            "canonical_field": "northbound_net_buy_amount",
            "chinese_name": "北向净买入",
            "field_type": "raw",
            "required_frequency": "daily",
            "local_status": "missing",
            "rqdata_candidate_function": "capital_flow",
            "rqdata_candidate_field": "northbound_net_buy_amount",
            "recommended_dataset_name": "capital_flow_1d",
            "notes": "",
        },
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


class FakeRQData:
    def __init__(self, frame=None, exc=None):
        self.frame = frame
        self.exc = exc

    def get_factor(self, *args, **kwargs):
        if self.exc:
            raise self.exc
        return self.frame


class FakeProbe(RQDataFieldProbe):
    def __init__(self, fake):
        super().__init__()
        self.fake = fake

    def init(self):
        return self.fake


def _probe_row():
    return {
        "priority": "P0",
        "data_pack": "valuation_core",
        "canonical_field": "pe_ttm",
        "chinese_name": "滚动市盈率",
        "field_type": "raw",
        "required_frequency": "daily",
        "local_status": "missing",
        "rqdata_candidate_function": "get_factor",
        "rqdata_candidate_field": "pe_ttm",
        "recommended_dataset_name": "valuation_1d",
        "notes": "",
    }


def test_p0_raw_filter_excludes_derived_and_non_p0(tmp_path):
    path = tmp_path / "raw.csv"
    _raw_csv(path)

    rows = load_p0_probe_inputs(path)

    assert [row["canonical_field"] for row in rows] == ["pe_ttm"]


def test_available_sample_records_available():
    probe = FakeProbe(FakeRQData(pd.DataFrame({"pe_ttm": [1.0, None, 2.0]})))

    row = probe.probe_row(_probe_row())

    assert row["rqdata_probe_status"] == "available"
    assert row["sample_row_count"] == 3
    assert row["sample_non_null_count"] == 2
    assert row["recommended_action_after_probe"] == "backfill_p0"


def test_empty_sample_records_available_but_empty():
    probe = FakeProbe(FakeRQData(pd.DataFrame({"pe_ttm": [None, None]})))

    row = probe.probe_row(_probe_row())

    assert row["rqdata_probe_status"] == "available_but_empty_sample"
    assert row["recommended_action_after_probe"] == "source_audit_needed"


def test_permission_error_records_permission_required():
    probe = FakeProbe(FakeRQData(exc=RuntimeError("permission denied for license key abcdefghijklmnopqrstuvwxyz123456")))

    row = probe.probe_row(_probe_row())

    assert row["rqdata_probe_status"] == "permission_required"
    assert row["permission_status"] == "blocked"
    assert "abcdefghijklmnopqrstuvwxyz123456" not in row["error_message_sanitized"]


def test_function_not_found_records_function_not_found():
    row = _probe_row()
    row["rqdata_candidate_function"] = "missing_api"
    probe = FakeProbe(FakeRQData())

    out = probe.probe_row(row)

    assert out["rqdata_probe_status"] == "function_not_found"
    assert out["recommended_action_after_probe"] == "external_source_required"


def test_sanitize_error_message_masks_tokens(monkeypatch):
    monkeypatch.setenv("RQDATAC_KEY", "x" * 40)

    text = sanitize_error_message("token=" + "x" * 40)

    assert "x" * 40 not in text
    assert "<redacted>" in text


def test_probe_columns_declared():
    assert "rqdata_probe_status" in P0_PROBE_COLUMNS
    assert "error_message_sanitized" in P0_PROBE_COLUMNS


def test_after_probe_plan_aggregates_pack():
    probe_rows = [
        {
            **{column: "" for column in P0_PROBE_COLUMNS},
            "priority": "P0",
            "data_pack": "valuation_core",
            "canonical_field": "pe_ttm",
            "rqdata_probe_status": "available",
            "recommended_action_after_probe": "backfill_p0",
        }
    ]
    derived_rows = [
        {
            "data_pack": "monthly_research_panel",
            "derived_field": "bm",
            "required_raw_fields": "equity_parent,market_cap",
        }
    ]

    plan = build_after_probe_plan(probe_rows, derived_rows)

    assert plan[0]["data_pack"] == "valuation_core"
    assert plan[0]["raw_fields_available_from_rqdata"] == "pe_ttm"
    assert plan[0]["go_or_no_go"] == "GO"
