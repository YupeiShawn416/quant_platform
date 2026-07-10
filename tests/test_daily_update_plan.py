import pandas as pd
import pytest

from rq_platform.etl import daily_update_core
from rq_platform.etl.daily_update_core import merge_partition_file, require_daily_update_confirmation, run_daily_update
from rq_platform.etl.daily_update_plan import build_daily_update_plan


def _write_calendar(root, dates):
    path = root / "trading_calendar"
    path.mkdir(parents=True)
    pd.DataFrame({"trade_date": dates, "is_open": [True] * len(dates)}).to_parquet(
        path / "trading_calendar.parquet", index=False
    )


def test_daily_update_plan_no_op_when_end_date_is_covered(tmp_path):
    root = tmp_path / "rqdata"
    _write_calendar(root, ["2026-07-10"])

    plan = build_daily_update_plan(end_date="2026-07-10", data_root=root)

    assert plan.no_op is True
    assert all(task.action == "no-op" for task in plan.tasks)


def test_daily_update_plan_next_day_after_latest(tmp_path):
    root = tmp_path / "rqdata"
    _write_calendar(root, ["2026-07-10"])

    plan = build_daily_update_plan(end_date="2026-07-11", datasets=["prices"], data_root=root)

    assert plan.no_op is False
    assert plan.start_date == "2026-07-11"
    assert plan.tasks[0].year == 2026
    assert plan.tasks[0].start_date == "2026-07-11"
    assert plan.tasks[0].end_date == "2026-07-11"


def test_daily_update_plan_cross_year_generates_year_tasks(tmp_path):
    root = tmp_path / "rqdata"
    _write_calendar(root, ["2026-12-30"])

    plan = build_daily_update_plan(end_date="2027-01-02", datasets=["prices"], data_root=root)

    assert [task.year for task in plan.tasks] == [2026, 2027]
    assert plan.tasks[0].start_date == "2026-12-31"
    assert plan.tasks[0].end_date == "2026-12-31"
    assert plan.tasks[1].start_date == "2027-01-01"
    assert plan.tasks[1].end_date == "2027-01-02"


def test_daily_update_dry_run_does_not_initialize_rqdata(monkeypatch):
    def fail_if_called():
        raise AssertionError("dry-run must not initialize RQData")

    monkeypatch.setattr(daily_update_core, "RQDataSource", fail_if_called)
    result = run_daily_update(
        start_date="2026-07-11",
        end_date="2026-07-11",
        datasets=["prices"],
        dry_run=True,
    )

    assert result["plan"].start_date == "2026-07-11"


def test_daily_update_requires_confirm_for_real_update():
    with pytest.raises(ValueError, match="confirm-daily-update"):
        require_daily_update_confirmation(dry_run=False, confirm_daily_update=False)


def test_merge_partition_file_deduplicates_trade_date_order_book_id(tmp_path):
    path = tmp_path / "year=2026.parquet"
    pd.DataFrame(
        {
            "trade_date": ["2026-07-10"],
            "order_book_id": ["000001.XSHE"],
            "close": [10.0],
        }
    ).to_parquet(path, index=False)

    merge_partition_file(
        pd.DataFrame(
            {
                "trade_date": ["2026-07-10", "2026-07-11"],
                "order_book_id": ["000001.XSHE", "000001.XSHE"],
                "close": [11.0, 12.0],
            }
        ),
        path,
        dedupe_keys=["trade_date", "order_book_id"],
    )

    result = pd.read_parquet(path)
    assert result["trade_date"].tolist() == ["2026-07-10", "2026-07-11"]
    assert result["close"].tolist() == [11.0, 12.0]
