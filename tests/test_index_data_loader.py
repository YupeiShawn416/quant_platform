import pandas as pd

from rq_platform.data.data_loader import DEFAULT_INDEX_PRICE_FIELDS, ResearchDataLoader
from rq_platform.settings import settings


def test_load_index_prices_reads_local_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    dataset_dir = tmp_path / "index_prices_1d"
    dataset_dir.mkdir()
    pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000300.XSHG",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000.0,
                "total_turnover": 100000.0,
                "num_trades": 10,
            },
            {
                "trade_date": "2025-01-03",
                "order_book_id": "000905.XSHG",
                "open": 200.0,
                "high": 201.0,
                "low": 199.0,
                "close": 200.5,
                "volume": 2000.0,
                "total_turnover": 200000.0,
                "num_trades": 20,
            },
        ]
    ).to_parquet(dataset_dir / "year=2025.parquet", index=False)

    frame = ResearchDataLoader().load_index_prices(
        index_ids=["000300.XSHG"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )

    assert len(frame) == 1
    assert frame.iloc[0]["order_book_id"] == "000300.XSHG"
    assert frame.iloc[0]["close"] == 100.5


def test_load_index_prices_returns_empty_frame_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))

    frame = ResearchDataLoader().load_index_prices(
        index_ids=["000300.XSHG"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )

    assert frame.empty
    assert list(frame.columns) == DEFAULT_INDEX_PRICE_FIELDS
