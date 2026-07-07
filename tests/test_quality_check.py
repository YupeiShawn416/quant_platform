import pandas as pd

from rq_platform.etl.quality_check import check_price_dataset


def test_check_price_dataset_summarizes_local_parquet(tmp_path):
    dataset_dir = tmp_path / "prices_1d_pre"
    dataset_dir.mkdir()
    frame = pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000001.XSHE",
                "adjust_type": "pre",
                "close": 10.0,
                "volume": 100.0,
            },
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000001.XSHE",
                "adjust_type": "pre",
                "close": 10.1,
                "volume": None,
            },
            {
                "trade_date": "2025-01-03",
                "order_book_id": "600000.XSHG",
                "adjust_type": "pre",
                "close": None,
                "volume": 200.0,
            },
        ]
    )
    frame.to_parquet(dataset_dir / "year=2025.parquet", index=False)

    result = check_price_dataset("pre", year=2025, data_root=tmp_path)

    assert result["dataset"] == "prices_1d_pre"
    assert result["file_exists"]
    assert result["rows"] == 3
    assert result["symbols"] == 2
    assert result["min_date"] == "2025-01-02"
    assert result["max_date"] == "2025-01-03"
    assert result["duplicate_keys"] == 1
    assert result["missing_close"] == 1
    assert result["missing_volume"] == 1
    assert result["daily_symbol_count_min"] == 1
    assert result["daily_symbol_count_max"] == 1


def test_check_price_dataset_missing_file_is_clear(tmp_path):
    result = check_price_dataset("none", year=2025, data_root=tmp_path)

    assert result["dataset"] == "prices_1d_none"
    assert not result["file_exists"]
    assert result["rows"] == 0
