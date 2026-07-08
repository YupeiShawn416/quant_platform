import pandas as pd

from rq_platform.data.data_loader import DEFAULT_VALUATION_FIELDS, ResearchDataLoader
from rq_platform.data_sources.rqdata_source import RQDataSource
from rq_platform.etl.update_valuation import write_valuation_dataset
from rq_platform.etl.valuation_quality_check import check_valuation_dataset
from rq_platform.settings import settings


def test_load_valuation_reads_local_parquet(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    dataset_dir = tmp_path / "valuation_1d"
    dataset_dir.mkdir()
    _valuation_frame().to_parquet(dataset_dir / "year=2025.parquet", index=False)

    frame = ResearchDataLoader().load_valuation(
        symbols=["AAA.X"],
        start_date="2025-01-01",
        end_date="2025-01-31",
        fields=["market_cap", "pe_ratio"],
    )

    assert len(frame) == 1
    assert list(frame.columns) == ["trade_date", "order_book_id", "market_cap", "pe_ratio"]
    assert frame.iloc[0]["market_cap"] == 100.0


def test_load_valuation_returns_empty_frame_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))

    frame = ResearchDataLoader().load_valuation(
        symbols=["AAA.X"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )

    assert frame.empty
    assert list(frame.columns) == DEFAULT_VALUATION_FIELDS


def test_check_valuation_dataset_reports_missing_and_duplicates(tmp_path):
    dataset_dir = tmp_path / "valuation_1d"
    dataset_dir.mkdir()
    frame = pd.concat([_valuation_frame(), _valuation_frame().iloc[[0]]], ignore_index=True)
    frame.loc[1, "pe_ratio"] = None
    frame.to_parquet(dataset_dir / "year=2025.parquet", index=False)

    result = check_valuation_dataset(year=2025, data_root=tmp_path)

    assert result["file_exists"]
    assert result["rows"] == 3
    assert result["symbols"] == 2
    assert result["duplicate_keys"] == 1
    assert result["missing_by_column"]["pe_ratio"] == 1
    assert result["daily_symbol_count_min"] == 2


def test_write_valuation_dataset_normalizes_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))

    path = write_valuation_dataset(_valuation_frame()[["trade_date", "order_book_id", "market_cap"]])
    loaded = pd.read_parquet(path)

    assert path == tmp_path / "valuation_1d" / "year=2025.parquet"
    assert list(loaded.columns) == DEFAULT_VALUATION_FIELDS
    assert loaded["market_cap"].tolist() == [100.0, 200.0]


def test_rqdata_source_normalizes_valuation_factor_and_turnover_frames():
    source = RQDataSource()
    factor_raw = pd.DataFrame(
        [
            {
                "order_book_id": "AAA.X",
                "date": "2025-01-02",
                "market_cap": 100.0,
                "market_cap_2": 80.0,
                "pe_ratio": 10.0,
                "pb_ratio": 1.0,
                "ps_ratio": 2.0,
                "pcf_ratio": 3.0,
            }
        ]
    ).set_index(["order_book_id", "date"])
    turnover_raw = pd.DataFrame(
        [{"order_book_id": "AAA.X", "tradedate": "2025-01-02", "today": 0.5}]
    ).set_index(["order_book_id", "tradedate"])

    factors = source._normalize_valuation_factor_frame(factor_raw)
    turnover = source._normalize_turnover_frame(turnover_raw)
    merged = factors.merge(turnover, on=["trade_date", "order_book_id"])

    assert merged.iloc[0]["trade_date"] == "2025-01-02"
    assert merged.iloc[0]["float_market_cap"] == 80.0
    assert merged.iloc[0]["turnover_rate"] == 0.5


def _valuation_frame():
    return pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "AAA.X",
                "market_cap": 100.0,
                "float_market_cap": 80.0,
                "pe_ratio": 10.0,
                "pb_ratio": 1.0,
                "ps_ratio": 2.0,
                "pcf_ratio": 3.0,
                "turnover_rate": 0.5,
            },
            {
                "trade_date": "2025-01-02",
                "order_book_id": "BBB.X",
                "market_cap": 200.0,
                "float_market_cap": 160.0,
                "pe_ratio": 20.0,
                "pb_ratio": 2.0,
                "ps_ratio": 4.0,
                "pcf_ratio": 6.0,
                "turnover_rate": 1.5,
            },
        ]
    )
