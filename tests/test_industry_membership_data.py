import pandas as pd

from rq_platform.data.data_loader import ResearchDataLoader
from rq_platform.data_sources.rqdata_source import RQDataSource
from rq_platform.etl.index_membership_quality_check import check_index_membership_dataset
from rq_platform.etl.industry_quality_check import check_industry_dataset
from rq_platform.etl.update_index_membership import write_index_components, write_index_weights
from rq_platform.etl.update_industry import write_industry_classification
from rq_platform.settings import settings


def test_rqdata_source_normalizes_industry_frame():
    raw = pd.DataFrame(
        [
            {"order_book_id": "000001.XSHE", "first_industry_code": "40", "first_industry_name": "银行"},
            {"order_book_id": "600519.XSHG", "first_industry_code": "36", "first_industry_name": "食品饮料"},
        ]
    ).set_index("order_book_id")

    frame = RQDataSource()._normalize_industry_frame(
        raw,
        trade_date="2025-01-02",
        source="citics_2019",
        level=1,
    )

    assert list(frame.columns) == [
        "trade_date",
        "order_book_id",
        "industry_system",
        "industry_level",
        "industry_code",
        "industry_name",
    ]
    assert frame.iloc[0]["trade_date"] == "2025-01-02"
    assert frame.iloc[0]["industry_name"] == "银行"


def test_industry_write_load_and_quality_check(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    path = write_industry_classification(_industry_frame(), year=2025)

    loaded = ResearchDataLoader().load_industry(
        symbols=["000001.XSHE"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )
    result = check_industry_dataset(year=2025, data_root=tmp_path)

    assert path == tmp_path / "industry_classification" / "year=2025.parquet"
    assert len(loaded) == 1
    assert loaded.iloc[0]["industry_name"] == "银行"
    assert result["rows"] == 2
    assert result["duplicate_keys"] == 0
    assert result["industry_count"] == 2


def test_index_membership_write_load_and_quality_check(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))
    write_index_components(_component_frame(), year=2025)
    write_index_weights(_weight_frame(), year=2025)

    components = ResearchDataLoader().load_index_components(
        index_ids=["000300.XSHG"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )
    weights = ResearchDataLoader().load_index_weights(
        index_ids=["000300.XSHG"],
        start_date="2025-01-01",
        end_date="2025-01-31",
    )
    result = check_index_membership_dataset(
        year=2025,
        data_root=tmp_path,
        expected_index_ids=["000300.XSHG"],
    )

    assert len(components) == 2
    assert len(weights) == 2
    assert result["component_rows"] == 2
    assert result["weight_rows"] == 2
    assert result["component_duplicate_keys"] == 0
    assert result["weight_duplicate_keys"] == 0
    assert result["daily_component_count_min"]["000300.XSHG"] == 2
    assert result["daily_weight_sum_min"]["000300.XSHG"] == 1.0


def _industry_frame():
    return pd.DataFrame(
        [
            {
                "trade_date": "2025-01-02",
                "order_book_id": "000001.XSHE",
                "industry_system": "citics_2019",
                "industry_level": 1,
                "industry_code": "40",
                "industry_name": "银行",
            },
            {
                "trade_date": "2025-01-02",
                "order_book_id": "600519.XSHG",
                "industry_system": "citics_2019",
                "industry_level": 1,
                "industry_code": "36",
                "industry_name": "食品饮料",
            },
        ]
    )


def _component_frame():
    return pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "index_id": "000300.XSHG", "order_book_id": "000001.XSHE"},
            {"trade_date": "2025-01-02", "index_id": "000300.XSHG", "order_book_id": "600519.XSHG"},
        ]
    )


def _weight_frame():
    return pd.DataFrame(
        [
            {"trade_date": "2025-01-02", "index_id": "000300.XSHG", "order_book_id": "000001.XSHE", "weight": 0.4},
            {"trade_date": "2025-01-02", "index_id": "000300.XSHG", "order_book_id": "600519.XSHG", "weight": 0.6},
        ]
    )
