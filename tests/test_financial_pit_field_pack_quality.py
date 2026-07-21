import pandas as pd

from rq_platform.etl.financial_pit_field_pack_quality import (
    check_financial_pit_field_pack,
    reconcile_with_financial_pit_quarterly,
    summarize_financial_pit_field_pack,
)


def _valid_frame():
    return pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "600519.XSHG"],
            "report_period": ["2024q4", "2024q4"],
            "quarter": ["2024q4", "2024q4"],
            "info_date": ["2025-03-20", "2025-03-21"],
            "rice_create_tm": ["2025-03-20 10:00:00", "2025-03-21 10:00:00"],
            "if_adjusted": [False, False],
            "statement_type": [None, None],
            "revenue": [100.0, 200.0],
            "total_liabilities": [50.0, 80.0],
        }
    )


def test_missing_info_date_has_quality_issue():
    frame = _valid_frame().drop(columns=["info_date"])

    issues = check_financial_pit_field_pack(frame)

    assert any(issue.check == "required_columns" for issue in issues)


def test_duplicate_key_has_quality_issue():
    frame = pd.concat([_valid_frame().iloc[[0]], _valid_frame().iloc[[0]]], ignore_index=True)

    issues = check_financial_pit_field_pack(frame)

    assert any(issue.check == "duplicate_key" for issue in issues)


def test_all_empty_field_not_ready():
    frame = _valid_frame()
    frame["revenue"] = None

    issues = check_financial_pit_field_pack(frame)
    summary = summarize_financial_pit_field_pack(frame)

    assert any(issue.check == "revenue_all_empty" for issue in issues)
    assert next(item for item in summary["field_stats"] if item["canonical_field"] == "revenue")["ready"] is False


def test_reconcile_with_old_dataset(tmp_path):
    old_dir = tmp_path / "financial_pit_quarterly" / "year=2025"
    old_dir.mkdir(parents=True)
    pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE"],
            "quarter": ["2024q4"],
            "info_date": ["2025-03-20"],
            "rice_create_tm": ["2025-03-20 10:00:00"],
            "if_adjusted": [False],
            "revenue": [100.0],
        }
    ).to_parquet(old_dir / "part.parquet", index=False)
    frame = _valid_frame().iloc[[0]]

    result = reconcile_with_financial_pit_quarterly(frame, tmp_path)

    assert result["status"] == "success"
    assert result["overlap_fields"] == ["revenue"]
    assert result["samples"][0]["max_abs_diff"] == 0.0
