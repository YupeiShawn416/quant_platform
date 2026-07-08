import pandas as pd

from rq_platform.etl.index_quality_check import check_index_price_dataset


def test_check_index_price_dataset_finds_missing_close_and_duplicates(tmp_path):
    dataset_dir = tmp_path / "index_prices_1d"
    dataset_dir.mkdir()
    pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000300.XSHG",
                "close": 100.0,
            },
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000300.XSHG",
                "close": None,
            },
            {
                "trade_date": "2025-01-03",
                "order_book_id": "000905.XSHG",
                "close": 200.0,
            },
        ]
    ).to_parquet(dataset_dir / "year=2025.parquet", index=False)

    result = check_index_price_dataset(
        year=2025,
        data_root=tmp_path,
        expected_index_ids=["000300.XSHG", "000905.XSHG", "000852.XSHG"],
    )

    assert result["dataset"] == "index_prices_1d"
    assert result["file_exists"]
    assert result["rows"] == 3
    assert result["indices"] == 2
    assert result["missing_indices"] == ["000852.XSHG"]
    assert result["min_date"] == "2025-01-02"
    assert result["max_date"] == "2025-01-03"
    assert result["duplicate_keys"] == 1
    assert result["missing_close"] == 1
    assert result["per_index_rows"]["000300.XSHG"] == 2
    assert result["per_index_close_missing"]["000300.XSHG"] == 1


def test_check_index_price_dataset_missing_file_is_clear(tmp_path):
    result = check_index_price_dataset(year=2025, data_root=tmp_path)

    assert result["dataset"] == "index_prices_1d"
    assert not result["file_exists"]
    assert result["rows"] == 0
