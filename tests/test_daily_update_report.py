from dataclasses import dataclass

from rq_platform.etl.daily_update_plan import DailyUpdatePlan
from rq_platform.etl.daily_update_report import build_daily_update_report


@dataclass
class _Result:
    dataset: str
    status: str
    row_count: int = 0
    error: str = ""

    def to_dict(self):
        return {
            "run_id": "run_1",
            "dataset": self.dataset,
            "start_date": "2026-07-11",
            "end_date": "2026-07-11",
            "year": 2026,
            "status": self.status,
            "row_count": self.row_count,
            "output_files": "",
            "error": self.error,
        }


@dataclass
class _Issue:
    dataset: str
    severity: str
    message: str

    def to_dict(self):
        return {"dataset": self.dataset, "severity": self.severity, "message": self.message, "path": ""}


def _plan(no_op=False):
    return DailyUpdatePlan(
        start_date="2026-07-11",
        end_date="2026-07-11",
        latest_date="2026-07-10",
        no_op=no_op,
        tasks=[],
    )


def _clean_reconcile(**overrides):
    data = {"mismatch_datasets": [], "zero_row_suspect_rows": [], "datasets": []}
    data.update(overrides)
    return data


def test_daily_update_report_success_recommends_rsync(monkeypatch):
    monkeypatch.setattr("rq_platform.etl.daily_update_report.reconcile_daily_update_coverage", lambda **kwargs: _clean_reconcile())
    report = build_daily_update_report(
        plan=_plan(),
        results=[_Result("prices", "success", 10)],
        quality_issues=[],
    )

    assert report["status"] == "success"
    assert report["recommend_rsync"] is True
    assert report["quality_issues_count"] == 0


def test_daily_update_report_failed_dataset_blocks_rsync(monkeypatch):
    monkeypatch.setattr("rq_platform.etl.daily_update_report.reconcile_daily_update_coverage", lambda **kwargs: _clean_reconcile())
    report = build_daily_update_report(
        plan=_plan(),
        results=[_Result("prices", "failed", error="boom")],
        quality_issues=[],
    )

    assert report["status"] == "failed"
    assert report["failed_datasets"] == ["prices"]
    assert report["recommend_rsync"] is False


def test_daily_update_report_no_op_does_not_recommend_rsync(monkeypatch):
    monkeypatch.setattr("rq_platform.etl.daily_update_report.reconcile_daily_update_coverage", lambda **kwargs: _clean_reconcile())
    report = build_daily_update_report(
        plan=_plan(no_op=True),
        results=[],
        quality_issues=[],
    )

    assert report["status"] == "success"
    assert report["recommend_rsync"] is False


def test_daily_update_report_quality_error_marks_failed(monkeypatch):
    monkeypatch.setattr("rq_platform.etl.daily_update_report.reconcile_daily_update_coverage", lambda **kwargs: _clean_reconcile())
    report = build_daily_update_report(
        plan=_plan(),
        results=[_Result("prices", "success", 10)],
        quality_issues=[_Issue("prices", "error", "duplicate")],
    )

    assert report["status"] == "failed"
    assert report["quality_issues_count"] == 1
    assert report["quality_error_count"] == 1


def test_daily_update_report_mismatch_blocks_rsync(monkeypatch):
    monkeypatch.setattr(
        "rq_platform.etl.daily_update_report.reconcile_daily_update_coverage",
        lambda **kwargs: _clean_reconcile(mismatch_datasets=["prices"]),
    )

    report = build_daily_update_report(
        plan=_plan(),
        results=[_Result("prices", "success", 10)],
        quality_issues=[],
    )

    assert report["status"] == "failed"
    assert report["recommend_rsync"] is False
    assert report["status_mismatch_datasets"] == ["prices"]
