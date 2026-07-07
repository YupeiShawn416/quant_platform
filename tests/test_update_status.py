from rq_platform.etl.update_status import append_status, is_batch_done, load_status


def test_update_status_round_trip_and_done_semantics(tmp_path):
    status_path = tmp_path / "update_logs" / "daily_prices_2025_status.csv"

    append_status(
        status_path,
        {
            "dataset": "prices_1d_pre",
            "adjust_type": "pre",
            "year": 2025,
            "batch_id": 0,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "symbol_count": 300,
            "status": "success",
            "row_count": 100,
            "output_files": "year=2025.parquet",
        },
    )
    append_status(
        status_path,
        {
            "dataset": "prices_1d_pre",
            "adjust_type": "pre",
            "year": 2025,
            "batch_id": 1,
            "status": "failed",
            "error": "RuntimeError: test",
        },
    )

    status = load_status(status_path)

    assert len(status) == 2
    assert is_batch_done(status, "pre", 2025, 0)
    assert not is_batch_done(status, "pre", 2025, 1)
    assert not is_batch_done(status, "none", 2025, 0)


def test_load_status_missing_file_returns_empty_frame(tmp_path):
    status = load_status(tmp_path / "missing.csv")

    assert status.empty
    assert "status" in status.columns
