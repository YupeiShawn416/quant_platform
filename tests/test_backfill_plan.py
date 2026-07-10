import pytest

from rq_platform.etl.backfill_core import run_core_backfill
from rq_platform.etl.backfill_plan import build_backfill_plan, require_full_backfill_confirmation


def test_dry_run_plan_does_not_require_rqdata(tmp_path):
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
