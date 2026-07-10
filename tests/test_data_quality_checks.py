import pandas as pd

from rq_platform.etl.data_quality_checks import (
    check_duplicate_keys,
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


def test_server_sync_manifest_contains_rsync_paths(tmp_path):
    manifest = render_server_sync_manifest(local_data_root=tmp_path / "rqdata")

    assert "rsync -avz" in manifest
    assert "prices_1d_pre" in manifest
    assert "/opt/quant_platform/data/research_data/rqdata/" in manifest
