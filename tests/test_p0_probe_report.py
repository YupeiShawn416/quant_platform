from __future__ import annotations

import json

import pandas as pd

from rq_platform.research.rqdata_field_probe import (
    AFTER_PROBE_PLAN_COLUMNS,
    P0_PROBE_COLUMNS,
    ProbeConfig,
    run_p0_rqdata_probe,
)


def _write_stage33_inputs(tmp_path):
    raw = pd.DataFrame(
        [
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
        ]
    )
    derived = pd.DataFrame(
        [
            {
                "priority": "P0",
                "data_pack": "monthly_research_panel",
                "derived_field": "bm",
                "chinese_name": "账面市值比",
                "required_frequency": "monthly",
                "formula": "book / market_cap",
                "required_raw_fields": "equity_parent,market_cap",
                "current_raw_field_status": "blocked_missing_raw",
                "missing_raw_fields": "equity_parent",
                "recommended_materialization": "monthly",
                "notes": "",
            }
        ]
    )
    raw_csv = tmp_path / "raw.csv"
    derived_csv = tmp_path / "derived.csv"
    raw.to_csv(raw_csv, index=False)
    derived.to_csv(derived_csv, index=False)
    return raw_csv, derived_csv


def test_disabled_probe_writes_not_probed_outputs(tmp_path):
    raw_csv, derived_csv = _write_stage33_inputs(tmp_path)

    result = run_p0_rqdata_probe(
        ProbeConfig(
            stage33_raw_csv=raw_csv,
            stage33_derived_csv=derived_csv,
            output_dir=tmp_path,
            enable_rqdata_probe=False,
        )
    )

    assert result["probe_rows"][0]["rqdata_probe_status"] == "not_probed"
    assert result["rqdata_probe_enabled"] is False
    probe_csv = pd.read_csv(tmp_path / "research_report_p0_rqdata_probe.csv")
    plan_json = json.loads((tmp_path / "research_report_data_backfill_plan_after_probe.json").read_text(encoding="utf-8"))
    plan_md = (tmp_path / "research_report_data_backfill_plan_after_probe.md").read_text(encoding="utf-8")

    assert list(probe_csv.columns) == P0_PROBE_COLUMNS
    assert set(plan_json[0]) == set(AFTER_PROBE_PLAN_COLUMNS)
    assert plan_md.startswith("# Research Report Backfill Plan After P0 Probe")


def test_json_and_markdown_outputs_complete(tmp_path):
    raw_csv, derived_csv = _write_stage33_inputs(tmp_path)

    run_p0_rqdata_probe(
        ProbeConfig(
            stage33_raw_csv=raw_csv,
            stage33_derived_csv=derived_csv,
            output_dir=tmp_path,
            enable_rqdata_probe=False,
        )
    )

    rows = json.loads((tmp_path / "research_report_p0_rqdata_probe.json").read_text(encoding="utf-8"))
    md = (tmp_path / "research_report_p0_rqdata_probe.md").read_text(encoding="utf-8")

    assert set(rows[0]) == set(P0_PROBE_COLUMNS)
    assert "P0 Missing Raw Fields RQData Probe" in md
