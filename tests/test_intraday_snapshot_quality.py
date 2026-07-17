import pandas as pd

from rq_platform.etl.intraday_snapshot_quality import (
    check_intraday_snapshot_quality,
    check_intraday_snapshot_status_log,
)


def test_intraday_snapshot_quality_detects_duplicate_and_outside_time(tmp_path):
    path = tmp_path / "intraday_snapshots" / "year=2025"
    path.mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "datetime": "2025-01-02 09:55:00", "snapshot_time": "09:55", "order_book_id": "000001.XSHE", "close": 10, "volume": 1, "total_turnover": 1},
            {"trade_date": "2025-01-02", "datetime": "2025-01-02 09:55:00", "snapshot_time": "09:55", "order_book_id": "000001.XSHE", "close": 10, "volume": 1, "total_turnover": 1},
            {"trade_date": "2025-01-02", "datetime": "2025-01-02 10:01:00", "snapshot_time": "10:01", "order_book_id": "000002.XSHE", "close": 10, "volume": 1, "total_turnover": 1},
        ]
    ).to_parquet(path / "month=01.parquet", index=False)

    issues = check_intraday_snapshot_quality(tmp_path, min_symbols_per_snapshot=0)
    messages = [issue.message for issue in issues]

    assert any("duplicate keys" in message for message in messages)
    assert any("outside snapshot_time" in message for message in messages)


def test_intraday_snapshot_quality_detects_bad_prices_and_core_missing(tmp_path):
    path = tmp_path / "intraday_snapshots" / "year=2025"
    path.mkdir(parents=True)
    pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "datetime": "2025-01-02 09:45:00", "snapshot_time": "09:45", "order_book_id": "000001.XSHE", "close": 0, "volume": -1, "total_turnover": -1},
        ]
    ).to_parquet(path / "month=01.parquet", index=False)

    issues = check_intraday_snapshot_quality(tmp_path, min_symbols_per_snapshot=0)
    messages = [issue.message for issue in issues]

    assert any("close <= 0" in message for message in messages)
    assert any("volume < 0" in message for message in messages)
    assert any("total_turnover < 0" in message for message in messages)
    assert any("missing core snapshot_time" in message for message in messages)


def test_intraday_snapshot_status_success_zero_is_error(tmp_path):
    path = tmp_path / "status.csv"
    pd.DataFrame(
        [
            {
                "run_id": "r1",
                "dataset": "intraday_snapshots",
                "start_date": "2025-01-02",
                "end_date": "2025-01-02",
                "snapshot_time": "09:55",
                "status": "success",
                "row_count": 0,
            }
        ]
    ).to_csv(path, index=False)

    issues = check_intraday_snapshot_status_log(path)

    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert "row_count=0" in issues[0].message
