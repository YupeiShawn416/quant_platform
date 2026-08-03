import pandas as pd
import pytest

from rq_platform.etl.intraday_snapshot_plan import (
    CORE_SNAPSHOT_TIMES,
    build_intraday_snapshot_plan,
    normalize_snapshot_times,
)


def test_intraday_snapshot_plan_dry_run_month_task(tmp_path):
    plan = build_intraday_snapshot_plan(
        start_date="2025-01-01",
        end_date="2025-01-10",
        data_root=tmp_path,
        dry_run=True,
    )

    assert plan.dry_run is True
    assert plan.tasks[0].year == 2025
    assert plan.tasks[0].month == 1
    assert "intraday_snapshots/year=2025/month=01.parquet" in plan.tasks[0].output_path


def test_intraday_snapshot_plan_cross_year_generates_month_tasks(tmp_path):
    plan = build_intraday_snapshot_plan(
        start_date="2025-12-31",
        end_date="2026-01-02",
        data_root=tmp_path,
    )

    assert [(task.year, task.month, task.start_date, task.end_date) for task in plan.tasks] == [
        (2025, 12, "2025-12-31", "2025-12-31"),
        (2026, 1, "2026-01-01", "2026-01-02"),
    ]


def test_intraday_snapshot_plan_skips_existing_complete_partition(tmp_path):
    path = tmp_path / "intraday_snapshots" / "year=2025"
    path.mkdir(parents=True)
    rows = []
    for day in ["2025-01-01", "2025-01-02"]:
        for time in ["09:45", "09:50", "09:55", "10:00", "14:30", "14:45", "14:55"]:
            rows.append({"trade_date": day, "snapshot_time": time, "order_book_id": "000001.XSHE"})
    pd.DataFrame(rows).to_parquet(path / "month=01.parquet", index=False)

    plan = build_intraday_snapshot_plan(
        start_date="2025-01-01",
        end_date="2025-01-02",
        data_root=tmp_path,
    )

    assert plan.no_op is True
    assert plan.tasks[0].should_skip is True
    assert plan.tasks[0].reason == "exists"


def test_snapshot_time_validation_and_core_points():
    assert normalize_snapshot_times("10:00,09:55") == ["09:55", "10:00"]
    assert normalize_snapshot_times("09:50,09:45") == ["09:45", "09:50"]
    assert CORE_SNAPSHOT_TIMES == ["09:55", "10:00"]
    with pytest.raises(ValueError, match="unsupported snapshot_time"):
        normalize_snapshot_times("09:31")
