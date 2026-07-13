import pandas as pd
import pytest

from rq_platform.data.query_service import (
    MAX_QUERY_LIMIT,
    DataQueryError,
    DataQueryService,
    DatasetNotFoundError,
)
from rq_platform.settings import settings


def test_query_service_filters_fields_limit_and_offset(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    _write_fixture(tmp_path)

    frame, has_more = DataQueryService().query(
        "prices_1d_pre",
        start_date="2025-01-02",
        end_date="2025-01-04",
        order_book_ids=["000001.XSHE"],
        fields=["trade_date", "order_book_id", "close"],
        limit=1,
        offset=1,
    )

    assert has_more is True
    assert list(frame.columns) == ["trade_date", "order_book_id", "close"]
    assert frame.to_dict(orient="records") == [
        {"trade_date": "2025-01-03", "order_book_id": "000001.XSHE", "close": 10.2}
    ]


def test_query_service_cross_year_partition_query(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    _write_fixture(tmp_path)

    frame, has_more = DataQueryService().query(
        "prices_1d_pre",
        start_date="2025-12-31",
        end_date="2026-01-02",
        order_book_ids=["000001.XSHE"],
        limit=10,
    )

    assert has_more is False
    assert frame["trade_date"].tolist() == ["2025-12-31", "2026-01-02"]


def test_query_service_rejects_bad_limit_dataset_and_field(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    _write_fixture(tmp_path)

    with pytest.raises(DataQueryError, match=str(MAX_QUERY_LIMIT)):
        DataQueryService().query("prices_1d_pre", limit=MAX_QUERY_LIMIT + 1)
    with pytest.raises(DatasetNotFoundError):
        DataQueryService().query("missing")
    with pytest.raises(DataQueryError, match="unknown fields"):
        DataQueryService().query("prices_1d_pre", fields=["missing"])


def test_query_service_coverage_and_schema(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    _write_fixture(tmp_path)

    coverage = DataQueryService().coverage()
    schema = DataQueryService().schema("prices_1d_pre")

    prices = next(item for item in coverage["datasets"] if item["dataset"] == "prices_1d_pre")
    assert coverage["supported_start_date"] == "2016-01-04"
    assert prices["years"] == [2025, 2026]
    assert prices["rows"] == 6
    assert {field["name"] for field in schema} >= {"trade_date", "order_book_id", "close"}


def _patch_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "rqdata"))


def _write_fixture(tmp_path):
    root = tmp_path / "rqdata"
    (root / "prices_1d_pre").mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-03", "2025-01-04", "2025-12-31"],
            "order_book_id": ["000001.XSHE", "000001.XSHE", "000001.XSHE", "000001.XSHE"],
            "close": [10.0, 10.2, 10.4, 11.0],
            "volume": [100, 110, 120, 130],
        }
    ).to_parquet(root / "prices_1d_pre" / "year=2025.parquet", index=False)
    pd.DataFrame(
        {
            "trade_date": ["2026-01-02", "2026-01-05"],
            "order_book_id": ["000001.XSHE", "600519.XSHG"],
            "close": [11.2, 1500.0],
            "volume": [140, 200],
        }
    ).to_parquet(root / "prices_1d_pre" / "year=2026.parquet", index=False)
    (root / "trading_calendar").mkdir()
    pd.DataFrame({"trade_date": ["2025-01-02", "2025-01-03"]}).to_parquet(
        root / "trading_calendar" / "trading_calendar.parquet",
        index=False,
    )
