import pandas as pd

from rq_platform.etl.intraday_snapshot_quality import IntradaySnapshotIssue
from rq_platform.etl.intraday_snapshot_report import (
    build_intraday_snapshot_report,
    write_intraday_snapshot_coverage_report,
    write_intraday_snapshot_quality_report,
)


def test_intraday_snapshot_report_success_and_failed_status():
    coverage = pd.DataFrame([{"year": 2025, "month": 1, "snapshot_time": "09:55", "rows": 1}])

    success = build_intraday_snapshot_report(quality_issues=[], coverage=coverage)
    failed = build_intraday_snapshot_report(
        quality_issues=[IntradaySnapshotIssue("intraday_snapshots", "error", "duplicate")],
        coverage=coverage,
    )

    assert success["status"] == "success"
    assert failed["status"] == "failed"
    assert failed["quality_error_count"] == 1


def test_intraday_snapshot_reports_write_files(tmp_path):
    data_root = tmp_path / "rqdata"
    path = data_root / "intraday_snapshots" / "year=2025"
    path.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02"],
            "datetime": ["2025-01-02 09:55:00"],
            "snapshot_time": ["09:55"],
            "order_book_id": ["000001.XSHE"],
            "close": [10.0],
        }
    ).to_parquet(path / "month=01.parquet", index=False)

    coverage_report = write_intraday_snapshot_coverage_report(data_root=data_root, output_dir=tmp_path / "reports")
    quality_report = write_intraday_snapshot_quality_report(quality_issues=[], output_dir=tmp_path / "reports")

    assert (tmp_path / "reports" / "intraday_snapshot_coverage.json").exists()
    assert (tmp_path / "reports" / "intraday_snapshot_quality.json").exists()
    assert coverage_report["rows"] == 1
    assert quality_report["status"] == "success"
