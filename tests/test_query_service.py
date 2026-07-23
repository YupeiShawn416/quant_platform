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


def test_query_service_supported_end_date_uses_complete_core_coverage(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    row = [{"trade_date": "2026-07-14", "order_book_id": "600519.XSHG", "close": 1500.0}]
    for dataset in ["prices_1d_pre", "prices_1d_none", "index_prices_1d", "tradability_1d", "valuation_1d"]:
        (root / dataset).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(row).to_parquet(root / dataset / "year=2026.parquet", index=False)

    service = DataQueryService()

    assert service.coverage()["supported_end_date"] == "2026-07-14"
    frame, _ = service.query("prices_1d_pre", start_date="2026-07-14", end_date="2026-07-14")
    assert len(frame) == 1


def test_query_service_exposes_financial_pit_field_pack(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    path = root / "financial_pit_field_pack" / "year=2026"
    path.mkdir(parents=True)
    pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "600519.XSHG"],
            "report_period": ["2025q4", "2025q4"],
            "info_date": ["2026-04-30", "2026-04-30"],
            "revenue": [100.0, 200.0],
            "net_profit": [10.0, 20.0],
        }
    ).to_parquet(path / "financial_pit_field_pack.parquet", index=False)

    service = DataQueryService()
    coverage = service.dataset_coverage("financial_pit_field_pack")
    frame, has_more = service.query(
        "financial_pit_field_pack",
        start_date="2026-04-30",
        end_date="2026-04-30",
        order_book_ids=["600519.XSHG"],
        fields=["order_book_id", "report_period", "info_date", "revenue"],
    )

    assert coverage["years"] == [2026]
    assert coverage["rows"] == 2
    assert has_more is False
    assert frame.to_dict(orient="records") == [
        {
            "order_book_id": "600519.XSHG",
            "report_period": "2025q4",
            "info_date": "2026-04-30",
            "revenue": 200.0,
        }
    ]


def test_query_service_exposes_financial_cashflow_field_pack(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    path = root / "financial_cashflow_field_pack" / "year=2026"
    path.mkdir(parents=True)
    pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "600519.XSHG"],
            "report_period": ["2025q4", "2025q4"],
            "info_date": ["2026-04-30", "2026-04-30"],
            "net_operate_cashflow_ttm": [100.0, 200.0],
            "cash_paid_for_asset": [10.0, 20.0],
        }
    ).to_parquet(path / "financial_cashflow_field_pack.parquet", index=False)

    service = DataQueryService()
    coverage = service.dataset_coverage("financial_cashflow_field_pack")
    frame, has_more = service.query(
        "financial_cashflow_field_pack",
        start_date="2026-04-30",
        end_date="2026-04-30",
        order_book_ids=["600519.XSHG"],
        fields=["order_book_id", "report_period", "info_date", "net_operate_cashflow_ttm"],
    )

    assert coverage["years"] == [2026]
    assert coverage["rows"] == 2
    assert has_more is False
    assert frame.to_dict(orient="records") == [
        {
            "order_book_id": "600519.XSHG",
            "report_period": "2025q4",
            "info_date": "2026-04-30",
            "net_operate_cashflow_ttm": 200.0,
        }
    ]


def test_query_service_exposes_nested_intraday_snapshots(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    path = root / "intraday_snapshots" / "year=2025"
    path.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2025-08-29", "2025-08-29"],
            "order_book_id": ["000001.XSHE", "600519.XSHG"],
            "last": [12.3, 1500.0],
        }
    ).to_parquet(path / "month=08.parquet", index=False)

    coverage = DataQueryService().dataset_coverage("intraday_snapshots")
    frame, _ = DataQueryService().query(
        "intraday_snapshots",
        start_date="2025-08-29",
        end_date="2025-08-29",
        order_book_ids=["000001.XSHE"],
    )

    assert coverage["years"] == [2025]
    assert coverage["rows"] == 2
    assert frame["order_book_id"].tolist() == ["000001.XSHE"]


def test_query_service_uses_dataset_specific_supported_range(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    for dataset, max_date in [
        ("prices_1d_pre", "2026-07-21"),
        ("prices_1d_none", "2026-07-21"),
        ("index_prices_1d", "2026-07-21"),
        ("tradability_1d", "2026-07-22"),
        ("valuation_1d", "2026-07-22"),
    ]:
        (root / dataset).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            [{"trade_date": max_date, "order_book_id": "000001.XSHE", "close": 10.0}]
        ).to_parquet(root / dataset / "year=2026.parquet", index=False)

    valuation, _ = DataQueryService().query("valuation_1d", start_date="2026-07-22", end_date="2026-07-22")
    with pytest.raises(DataQueryError, match="end_date must be <= 2026-07-21"):
        DataQueryService().query("prices_1d_pre", start_date="2026-07-22", end_date="2026-07-22")

    assert len(valuation) == 1


def test_query_service_filters_explicit_date_values(tmp_path, monkeypatch):
    _patch_data_root(tmp_path, monkeypatch)
    root = tmp_path / "rqdata"
    (root / "valuation_1d").mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2026-01-30", "2026-02-27", "2026-02-28", "2026-03-31"],
            "order_book_id": ["000001.XSHE"] * 4,
            "market_cap": [1.0, 2.0, 3.0, 4.0],
        }
    ).to_parquet(root / "valuation_1d" / "year=2026.parquet", index=False)

    frame, has_more = DataQueryService().query(
        "valuation_1d",
        date_values=["2026-01-30", "2026-03-31"],
        order_book_ids=["000001.XSHE"],
        fields=["trade_date", "order_book_id", "market_cap"],
    )

    assert has_more is False
    assert frame["trade_date"].tolist() == ["2026-01-30", "2026-03-31"]
    assert frame["market_cap"].tolist() == [1.0, 4.0]


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
