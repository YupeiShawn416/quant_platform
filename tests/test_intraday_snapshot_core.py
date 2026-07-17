import pandas as pd
import pytest

from rq_platform.etl import intraday_snapshot_core
from rq_platform.etl.intraday_snapshot_core import (
    merge_intraday_snapshot_partition,
    require_intraday_snapshot_confirmation,
    run_intraday_snapshot_backfill,
)
from rq_platform.settings import settings


def _write_instruments(root):
    path = root / "instruments"
    path.mkdir(parents=True)
    pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "600000.XSHG", "IF2401.CCFX"],
            "board_type": ["MainBoard", "MainBoard", "Future"],
        }
    ).to_parquet(path / "instruments.parquet", index=False)


class FakeSource:
    def get_intraday_snapshots(self, order_book_ids, start_date, end_date, snapshot_times):
        rows = []
        for symbol in order_book_ids:
            for ts in ["09:45", "09:55", "10:00", "10:01", "14:30", "14:45", "14:55"]:
                rows.append(
                    {
                        "datetime": f"{start_date} {ts}:00",
                        "order_book_id": symbol,
                        "close": 10.0,
                        "volume": 100,
                        "total_turnover": 1000,
                    }
                )
        return pd.DataFrame(rows)


def test_intraday_snapshot_dry_run_does_not_initialize_rqdata(monkeypatch, tmp_path):
    def fail_if_called():
        raise AssertionError("dry-run must not initialize RQData")

    monkeypatch.setattr(intraday_snapshot_core, "RQDataSource", fail_if_called)
    result = run_intraday_snapshot_backfill(
        start_date="2025-01-01",
        end_date="2025-01-10",
        dry_run=True,
    )

    assert result["plan"].dry_run is True


def test_intraday_snapshot_requires_confirm_for_real_update():
    with pytest.raises(ValueError, match="confirm-intraday-snapshot-backfill"):
        require_intraday_snapshot_confirmation(dry_run=False, confirm=False)


def test_intraday_snapshot_backfill_filters_six_snapshot_times(tmp_path, monkeypatch):
    root = tmp_path / "rqdata"
    _write_instruments(root)
    monkeypatch.setattr(settings, "data_root", str(root))
    monkeypatch.setattr(intraday_snapshot_core, "STATUS_PATH", root / "update_logs" / "intraday_snapshot_update_status.csv")
    monkeypatch.setattr(
        intraday_snapshot_core,
        "write_intraday_snapshot_quality_report",
        lambda **kwargs: {"status": "success"},
    )
    monkeypatch.setattr(intraday_snapshot_core, "check_intraday_snapshot_quality", lambda **kwargs: [])

    result = run_intraday_snapshot_backfill(
        start_date="2025-01-02",
        end_date="2025-01-02",
        batch_size=10,
        dry_run=False,
        confirm_intraday_snapshot_backfill=True,
        source=FakeSource(),
    )

    output = pd.read_parquet(root / "intraday_snapshots" / "year=2025" / "month=01.parquet")
    assert sorted(output["snapshot_time"].unique().tolist()) == ["09:45", "09:55", "10:00", "14:30", "14:45", "14:55"]
    assert "10:01" not in set(output["snapshot_time"])
    assert {item.status for item in result["results"]} == {"success"}


def test_merge_intraday_snapshot_partition_deduplicates(tmp_path):
    path = tmp_path / "month=01.parquet"
    first = pd.DataFrame(
        {
            "datetime": ["2025-01-02 09:55:00"],
            "order_book_id": ["000001.XSHE"],
            "close": [10.0],
            "volume": [100],
            "total_turnover": [1000],
        }
    )
    second = pd.DataFrame(
        {
            "datetime": ["2025-01-02 09:55:00", "2025-01-02 10:00:00"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "close": [11.0, 12.0],
            "volume": [110, 120],
            "total_turnover": [1100, 1200],
        }
    )

    merge_intraday_snapshot_partition(first, path)
    merge_intraday_snapshot_partition(second, path)

    output = pd.read_parquet(path)
    assert len(output) == 2
    assert output.loc[output["snapshot_time"].eq("09:55"), "close"].iloc[0] == 11.0
