import pandas as pd
import pytest

from rq_platform.etl.financial_pit_field_pack_plan import (
    build_financial_pit_field_pack_task,
    load_available_financial_pit_fields,
)


def test_loads_only_available_financial_pit_fields(tmp_path):
    path = tmp_path / "probe.csv"
    pd.DataFrame(
        [
            {
                "data_pack": "financial_pit_core",
                "rqdata_probe_status": "available",
                "field_type": "raw",
                "canonical_field": "revenue",
                "rqdata_candidate_function": "get_pit_financials_ex",
                "rqdata_candidate_field": "revenue",
            },
            {
                "data_pack": "financial_pit_core",
                "rqdata_probe_status": "unavailable",
                "field_type": "raw",
                "canonical_field": "accounts_receivable",
                "rqdata_candidate_function": "get_pit_financials_ex",
                "rqdata_candidate_field": "accounts_receivable",
            },
            {
                "data_pack": "valuation_core",
                "rqdata_probe_status": "available",
                "field_type": "raw",
                "canonical_field": "pe_ttm",
                "rqdata_candidate_function": "get_factor",
                "rqdata_candidate_field": "pe_ttm",
            },
        ]
    ).to_csv(path, index=False)

    fields = load_available_financial_pit_fields(path)

    assert [field.canonical_field for field in fields] == ["revenue"]


def test_task_plan_derives_quarters_and_calls():
    fields = load_available_financial_pit_fields_from_rows("revenue")

    task = build_financial_pit_field_pack_task(
        start_date="2024-01-01",
        end_date="2025-12-31",
        symbols=["000001.XSHE", "600519.XSHG", "300750.XSHE"],
        fields=fields,
        batch_size=2,
        dry_run=True,
        overwrite=False,
    )

    assert task.start_quarter == "2024q1"
    assert task.end_quarter == "2025q4"
    assert task.expected_api_calls == 2


def test_task_rejects_empty_fields():
    with pytest.raises(ValueError, match="No Stage 33B verified"):
        build_financial_pit_field_pack_task(
            start_date="2024-01-01",
            end_date="2025-12-31",
            symbols=["000001.XSHE"],
            fields=[],
            batch_size=2,
            dry_run=True,
            overwrite=False,
        )


def load_available_financial_pit_fields_from_rows(*names):
    from rq_platform.etl.financial_pit_field_pack_plan import FinancialPitField

    return [FinancialPitField(name, "get_pit_financials_ex", name) for name in names]
