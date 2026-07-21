import json

import pandas as pd

from rq_platform.etl.financial_pit_field_pack_report import (
    write_financial_pit_field_pack_coverage_report,
    write_financial_pit_field_pack_quality_report,
    write_financial_pit_field_pack_reconcile_report,
)


def _frame():
    return pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE"],
            "report_period": ["2024q4"],
            "quarter": ["2024q4"],
            "info_date": ["2025-03-20"],
            "rice_create_tm": ["2025-03-20 10:00:00"],
            "if_adjusted": [False],
            "statement_type": [None],
            "revenue": [100.0],
        }
    )


def test_quality_report_writes_json_and_markdown(tmp_path):
    paths = write_financial_pit_field_pack_quality_report(_frame(), tmp_path)

    payload = json.loads(paths["quality_json"].read_text(encoding="utf-8"))
    markdown = paths["quality_md"].read_text(encoding="utf-8")

    assert payload["status"] == "success"
    assert markdown.startswith("# Financial PIT Field Pack Quality")


def test_coverage_report_writes_summary(tmp_path):
    paths = write_financial_pit_field_pack_coverage_report(_frame(), tmp_path)

    payload = json.loads(paths["coverage_json"].read_text(encoding="utf-8"))

    assert payload["row_count"] == 1
    assert payload["field_stats"][0]["canonical_field"] == "revenue"


def test_reconcile_report_writes(tmp_path):
    paths = write_financial_pit_field_pack_reconcile_report(_frame(), tmp_path)

    assert paths["reconcile_md"].exists()
    assert paths["reconcile_json"].exists()
