import pandas as pd

from rq_platform.data.data_loader import DEFAULT_TRADABILITY_FIELDS, ResearchDataLoader
from rq_platform.etl.tradability_quality_check import check_tradability_dataset
from rq_platform.etl.update_tradability import build_tradability_dataset
from rq_platform.settings import settings


def test_build_tradability_dataset_from_prices_and_instruments(tmp_path):
    _write_base_tradability_inputs(tmp_path)

    frame = build_tradability_dataset(year=2025, data_root=tmp_path)

    row = frame[
        (frame["trade_date"] == "2025-01-02")
        & (frame["order_book_id"] == "AAA.X")
    ].iloc[0]
    assert bool(row["is_suspended"]) is False
    assert bool(row["can_buy"]) is False
    assert bool(row["can_sell"]) is True
    assert "limit_up" in row["reason"]

    suspended = frame[
        (frame["trade_date"] == "2025-01-03")
        & (frame["order_book_id"] == "AAA.X")
    ].iloc[0]
    assert bool(suspended["is_suspended"]) is True
    assert bool(suspended["can_buy"]) is False
    assert bool(suspended["can_sell"]) is False
    assert "suspended" in suspended["reason"]

    st = frame[
        (frame["trade_date"] == "2025-01-02")
        & (frame["order_book_id"] == "BBB.X")
    ].iloc[0]
    assert bool(st["is_st"]) is True
    assert bool(st["can_buy"]) is False
    assert bool(st["can_sell"]) is True
    assert "st" in st["reason"]


def test_load_tradability_reads_local_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    dataset_dir = tmp_path / "tradability_1d"
    dataset_dir.mkdir()
    pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "AAA.X",
                "is_listed": True,
                "is_suspended": False,
                "is_st": False,
                "can_buy": True,
                "can_sell": True,
                "reason": "",
            }
        ]
    ).to_parquet(dataset_dir / "year=2025.parquet", index=False)

    frame = ResearchDataLoader().load_tradability(
        symbols=["AAA.X"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )

    assert len(frame) == 1
    assert frame.iloc[0]["order_book_id"] == "AAA.X"
    assert bool(frame.iloc[0]["can_buy"]) is True


def test_load_tradability_returns_empty_frame_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))

    frame = ResearchDataLoader().load_tradability(
        symbols=["AAA.X"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )

    assert frame.empty
    assert list(frame.columns) == DEFAULT_TRADABILITY_FIELDS


def test_check_tradability_dataset_reports_reasons(tmp_path):
    dataset_dir = tmp_path / "tradability_1d"
    dataset_dir.mkdir()
    pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "AAA.X",
                "can_buy": False,
                "can_sell": True,
                "reason": "limit_up",
            },
            {
                "trade_date": "2025-01-02",
                "order_book_id": "AAA.X",
                "can_buy": False,
                "can_sell": False,
                "reason": "suspended",
            },
        ]
    ).to_parquet(dataset_dir / "year=2025.parquet", index=False)

    result = check_tradability_dataset(year=2025, data_root=tmp_path)

    assert result["file_exists"]
    assert result["rows"] == 2
    assert result["duplicate_keys"] == 1
    assert result["cannot_buy"] == 2
    assert result["cannot_sell"] == 1
    assert result["reason_counts"] == {"limit_up": 1, "suspended": 1}


def _write_base_tradability_inputs(tmp_path):
    calendar_dir = tmp_path / "trading_calendar"
    instruments_dir = tmp_path / "instruments"
    prices_dir = tmp_path / "prices_1d_pre"
    calendar_dir.mkdir()
    instruments_dir.mkdir()
    prices_dir.mkdir()
    pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "is_open": True},
            {"trade_date": "2025-01-03", "is_open": True},
        ]
    ).to_parquet(calendar_dir / "trading_calendar.parquet", index=False)
    pd.DataFrame(
        [
            {
                "order_book_id": "AAA.X",
                "listed_date": "2024-01-01",
                "de_listed_date": None,
                "special_type": "",
            },
            {
                "order_book_id": "BBB.X",
                "listed_date": "2024-01-01",
                "de_listed_date": None,
                "special_type": "ST",
            },
        ]
    ).to_parquet(instruments_dir / "instruments.parquet", index=False)
    pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "AAA.X",
                "close": 11.0,
                "limit_up": 11.0,
                "limit_down": 9.0,
            },
            {
                "trade_date": "2025-01-02",
                "order_book_id": "BBB.X",
                "close": 20.0,
                "limit_up": 22.0,
                "limit_down": 18.0,
            },
        ]
    ).to_parquet(prices_dir / "year=2025.parquet", index=False)
