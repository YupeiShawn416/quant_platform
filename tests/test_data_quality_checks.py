import pandas as pd

from rq_platform.etl.data_quality_checks import (
    check_duplicate_keys,
    check_expected_end_date_coverage,
    check_ohlc,
    run_data_quality_checks,
)
from rq_platform.etl.server_sync_manifest import render_server_sync_manifest


def test_quality_detects_duplicate_key():
    frame = pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-02"],
            "order_book_id": ["AAA.X", "AAA.X"],
            "close": [1, 2],
        }
    )

    issues = check_duplicate_keys("prices_1d_pre", frame)

    assert issues
    assert "duplicate" in issues[0].message


def test_quality_detects_ohlc_anomaly():
    frame = pd.DataFrame(
        {
            "trade_date": ["2025-01-02"],
            "order_book_id": ["AAA.X"],
            "open": [10],
            "high": [9],
            "low": [8],
            "close": [10],
        }
    )

    issues = check_ohlc("prices_1d_pre", frame)

    assert issues
    assert "OHLC" in issues[0].message


def test_quality_runs_on_tmp_parquet(tmp_path):
    root = tmp_path / "rqdata"
    dataset = root / "prices_1d_pre"
    dataset.mkdir(parents=True)
    frame = pd.DataFrame(
        {
            "trade_date": ["2025-01-02"],
            "order_book_id": ["AAA.X"],
            "open": [1],
            "high": [2],
            "low": [1],
            "close": [2],
            "volume": [100],
            "total_turnover": [200],
        }
    )
    frame.to_parquet(dataset / "year=2025.parquet", index=False)
    none_dataset = root / "prices_1d_none"
    none_dataset.mkdir(parents=True)
    frame.to_parquet(none_dataset / "year=2025.parquet", index=False)

    assert run_data_quality_checks(root) == []


def test_quality_catches_expected_end_date_gap(tmp_path):
    root = tmp_path / "rqdata"
    calendar = root / "trading_calendar"
    calendar.mkdir(parents=True)
    pd.DataFrame({"trade_date": ["2026-07-13"], "is_open": [True]}).to_parquet(
        calendar / "trading_calendar.parquet", index=False
    )
    for dataset in ["prices_1d_pre", "prices_1d_none", "index_prices_1d"]:
        path = root / dataset
        path.mkdir()
        pd.DataFrame({"trade_date": ["2026-07-09"], "order_book_id": ["000001.XSHE"]}).to_parquet(
            path / "year=2026.parquet", index=False
        )

    issues = check_expected_end_date_coverage(root, "2026-07-13")

    assert {issue.dataset for issue in issues} == {"prices_1d_pre", "prices_1d_none", "index_prices_1d"}


def test_quality_flags_zero_row_success_status(tmp_path):
    root = tmp_path / "rqdata"
    calendar = root / "trading_calendar"
    calendar.mkdir(parents=True)
    pd.DataFrame({"trade_date": ["2026-07-13"], "is_open": [True]}).to_parquet(
        calendar / "trading_calendar.parquet", index=False
    )
    status_dir = root / "update_logs"
    status_dir.mkdir()
    pd.DataFrame(
        [
            {
                "dataset": "prices",
                "status": "success",
                "row_count": 0,
                "start_date": "2026-07-13",
                "end_date": "2026-07-13",
            }
        ]
    ).to_csv(status_dir / "daily_update_status.csv", index=False)

    issues = run_data_quality_checks(root, expected_end_date=None)

    assert any("row_count=0" in issue.message for issue in issues)


def test_quality_ignores_zero_row_success_after_later_repair(tmp_path):
    root = tmp_path / "rqdata"
    calendar = root / "trading_calendar"
    calendar.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2026-07-11", "2026-07-13"],
            "is_open": [True, True],
        }
    ).to_parquet(calendar / "trading_calendar.parquet", index=False)
    status_dir = root / "update_logs"
    status_dir.mkdir()
    pd.DataFrame(
        [
            {
                "dataset": "prices",
                "status": "success",
                "row_count": 0,
                "start_date": "2026-07-11",
                "end_date": "2026-07-13",
            },
            {
                "dataset": "prices",
                "status": "success",
                "row_count": 20812,
                "start_date": "2026-07-10",
                "end_date": "2026-07-13",
            },
        ]
    ).to_csv(status_dir / "daily_update_status.csv", index=False)

    issues = run_data_quality_checks(root, expected_end_date=None)

    assert not any("row_count=0" in issue.message for issue in issues)


def test_server_sync_manifest_contains_rsync_paths(tmp_path):
    manifest = render_server_sync_manifest(local_data_root=tmp_path / "rqdata")

    assert "rsync -avz" in manifest
    assert "prices_1d_pre" in manifest
    assert "/opt/quant_platform/data/research_data/rqdata/" in manifest


def test_index_weights_duplicate_check_uses_index_id():
    frame = pd.DataFrame(
        {
            "trade_date": ["2020-01-02", "2020-01-02"],
            "index_id": ["000300.XSHG", "000905.XSHG"],
            "order_book_id": ["AAA.X", "AAA.X"],
            "weight": [0.1, 0.2],
        }
    )

    assert check_duplicate_keys("index_weights", frame) == []
