import pandas as pd

from rq_platform.etl.daily_update_reconcile import reconcile_daily_update_coverage, render_reconcile_markdown


def test_reconcile_lists_mismatch_and_zero_row_success(tmp_path):
    root = tmp_path / "rqdata"
    _write_partition(root, "prices_1d_pre", ["2026-07-09"])
    _write_partition(root, "prices_1d_none", ["2026-07-09"])
    status_path = root / "update_logs" / "daily_update_status.csv"
    status_path.parent.mkdir()
    pd.DataFrame(
        [
            {
                "run_id": "r1",
                "dataset": "prices",
                "start_date": "2026-07-10",
                "end_date": "2026-07-13",
                "year": 2026,
                "status": "success",
                "row_count": 0,
            }
        ]
    ).to_csv(status_path, index=False)

    report = reconcile_daily_update_coverage(
        status_path=status_path,
        data_root=root,
        expected_end_date="2026-07-13",
    )
    markdown = render_reconcile_markdown(report)

    assert "prices" in report["mismatch_datasets"]
    assert report["zero_row_suspect_rows"]
    assert report["recommend_rsync"] is False
    assert "prices" in markdown


def _write_partition(root, dataset, dates):
    path = root / dataset
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "trade_date": dates,
            "order_book_id": ["000001.XSHE"] * len(dates),
            "close": list(range(len(dates))),
        }
    ).to_parquet(path / "year=2026.parquet", index=False)
