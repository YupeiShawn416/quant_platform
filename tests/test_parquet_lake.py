import pandas as pd

from rq_platform.data.parquet_lake import read_single_file, write_by_year, write_single_file
from rq_platform.settings import settings


def test_write_single_file_uses_configured_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    frame = pd.DataFrame({"trade_date": ["2025-01-02"], "is_open": [True]})

    path = write_single_file(frame, "trading_calendar", "trading_calendar.parquet")
    loaded = read_single_file("trading_calendar", "trading_calendar.parquet")

    assert path == tmp_path / "trading_calendar" / "trading_calendar.parquet"
    assert loaded.to_dict("records") == frame.to_dict("records")


def test_write_by_year_splits_and_dedupes(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    first = pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000001.XSHE",
                "adjust_type": "pre",
                "close": 1.0,
            },
            {
                "trade_date": "2026-01-05",
                "order_book_id": "000001.XSHE",
                "adjust_type": "pre",
                "close": 2.0,
            },
        ]
    )
    second = pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000001.XSHE",
                "adjust_type": "pre",
                "close": 3.0,
            }
        ]
    )

    paths = write_by_year(
        first,
        "prices_1d_pre",
        dedupe_keys=["trade_date", "order_book_id", "adjust_type"],
    )
    write_by_year(
        second,
        "prices_1d_pre",
        dedupe_keys=["trade_date", "order_book_id", "adjust_type"],
    )
    loaded = pd.read_parquet(tmp_path / "prices_1d_pre" / "year=2025.parquet")

    assert paths == [
        tmp_path / "prices_1d_pre" / "year=2025.parquet",
        tmp_path / "prices_1d_pre" / "year=2026.parquet",
    ]
    assert loaded.to_dict("records") == [
        {
            "trade_date": "2025-01-02",
            "order_book_id": "000001.XSHE",
            "adjust_type": "pre",
            "close": 3.0,
        }
    ]
