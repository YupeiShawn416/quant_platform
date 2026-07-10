import pytest
import pandas as pd

from rq_platform.etl import backfill_core
from rq_platform.etl.backfill_core import merge_trading_calendar_file, run_core_backfill
from rq_platform.etl.backfill_plan import build_backfill_plan, require_full_backfill_confirmation


def test_dry_run_plan_does_not_require_rqdata(monkeypatch):
    def fail_if_called():
        raise AssertionError("dry-run must not initialize RQDataSource")

    monkeypatch.setattr(backfill_core, "RQDataSource", fail_if_called)

    result = run_core_backfill(
        start_date="2016-01-01",
        end_date="2017-12-31",
        datasets="prices,index_prices",
        dry_run=True,
    )

    assert len(result) == 4
    assert result[0]["dataset"] == "prices"


def test_full_backfill_requires_confirm():
    with pytest.raises(ValueError, match="confirm-full-backfill"):
        require_full_backfill_confirmation(
            start_date="2016-01-01",
            end_date="2025-12-31",
            dry_run=False,
            smoke=False,
            confirm_full_backfill=False,
        )


def test_existing_year_is_skipped_unless_force(tmp_path):
    existing = tmp_path / "rqdata" / "index_prices_1d"
    existing.mkdir(parents=True)
    (existing / "year=2020.parquet").write_bytes(b"placeholder")

    tasks = build_backfill_plan(
        start_date="2020-01-01",
        end_date="2020-12-31",
        datasets=["index_prices"],
        data_root=tmp_path / "rqdata",
    )

    assert tasks[0].should_skip is True
    assert tasks[0].reason == "exists"


def test_calendar_plan_uses_single_file_coverage(tmp_path):
    calendar_path = tmp_path / "rqdata" / "trading_calendar" / "trading_calendar.parquet"
    calendar_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2024-01-02", "2024-12-31", "2025-01-02", "2025-12-31"]),
            "is_open": [True, True, True, True],
        }
    ).to_parquet(calendar_path, index=False)

    tasks = build_backfill_plan(
        start_date="2016-01-01",
        end_date="2026-07-09",
        datasets=["calendar"],
        data_root=tmp_path / "rqdata",
    )

    assert len(tasks) == 1
    assert tasks[0].dataset == "calendar"
    assert tasks[0].year is None
    assert tasks[0].should_skip is False
    assert tasks[0].action == "extend"
    assert "missing_years=2016,2017,2018,2019,2020,2021,2022,2023,2026" in tasks[0].reason


def test_calendar_plan_skips_when_full_range_is_covered(tmp_path):
    calendar_path = tmp_path / "rqdata" / "trading_calendar" / "trading_calendar.parquet"
    calendar_path.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": pd.to_datetime([f"{year}-01-02" for year in range(2016, 2027)] + ["2026-07-09"]),
            "is_open": [True] * 12,
        }
    ).to_parquet(calendar_path, index=False)

    tasks = build_backfill_plan(
        start_date="2016-01-01",
        end_date="2026-07-09",
        datasets=["calendar"],
        data_root=tmp_path / "rqdata",
    )

    assert tasks[0].should_skip is True
    assert tasks[0].action == "skip"
    assert "covered" in tasks[0].reason


def test_calendar_plan_creates_when_missing(tmp_path):
    tasks = build_backfill_plan(
        start_date="2016-01-01",
        end_date="2026-07-09",
        datasets=["calendar"],
        data_root=tmp_path / "rqdata",
    )

    assert tasks[0].should_skip is False
    assert tasks[0].action == "create"
    assert "missing" in tasks[0].reason


def test_calendar_merge_deduplicates_and_sorts(tmp_path):
    calendar_path = tmp_path / "trading_calendar.parquet"
    pd.DataFrame(
        {
            "trade_date": ["2025-01-03", "2025-01-02"],
            "is_open": [True, True],
        }
    ).to_parquet(calendar_path, index=False)

    merge_trading_calendar_file(
        pd.DataFrame(
            {
                "trade_date": ["2025-01-02", "2024-12-31"],
                "is_open": [False, True],
            }
        ),
        calendar_path,
    )

    result = pd.read_parquet(calendar_path)
    assert result["trade_date"].tolist() == ["2024-12-31", "2025-01-02", "2025-01-03"]
    assert result["is_open"].tolist() == [True, False, True]


def test_instruments_existing_single_file_skips(tmp_path):
    instruments_path = tmp_path / "rqdata" / "instruments" / "instruments.parquet"
    instruments_path.parent.mkdir(parents=True)
    instruments_path.write_bytes(b"placeholder")

    tasks = build_backfill_plan(
        start_date="2016-01-01",
        end_date="2026-07-09",
        datasets=["instruments"],
        data_root=tmp_path / "rqdata",
    )

    assert len(tasks) == 1
    assert tasks[0].year is None
    assert tasks[0].should_skip is True
    assert tasks[0].action == "skip"


def test_partitioned_prices_plan_still_skips_existing_year_and_creates_missing(tmp_path):
    prices_pre = tmp_path / "rqdata" / "prices_1d_pre"
    prices_none = tmp_path / "rqdata" / "prices_1d_none"
    prices_pre.mkdir(parents=True)
    prices_none.mkdir(parents=True)
    (prices_pre / "year=2024.parquet").write_bytes(b"placeholder")
    (prices_none / "year=2024.parquet").write_bytes(b"placeholder")

    tasks = build_backfill_plan(
        start_date="2016-01-01",
        end_date="2024-12-31",
        years=[2016, 2024],
        datasets=["prices"],
        data_root=tmp_path / "rqdata",
    )

    by_year = {task.year: task for task in tasks}
    assert by_year[2016].should_skip is False
    assert by_year[2016].action == "create"
    assert by_year[2024].should_skip is True
    assert by_year[2024].reason == "exists"
