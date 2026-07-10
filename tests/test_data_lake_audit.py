import pandas as pd

from rq_platform.etl.data_lake_audit import audit_data_lake


def test_audit_identifies_year_coverage_and_missing_years(tmp_path):
    root = tmp_path / "rqdata"
    dataset = root / "prices_1d_pre"
    dataset.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2020-01-02", "2020-01-02"],
            "order_book_id": ["AAA.X", "BBB.X"],
            "adjust_type": ["pre", "pre"],
            "close": [1.0, 2.0],
        }
    ).to_parquet(dataset / "year=2020.parquet", index=False)

    result = audit_data_lake(
        data_root=root,
        datasets=["prices_1d_pre"],
        expected_start_year=2019,
        expected_end_year=2021,
    )

    year_row = result[result["year"] == 2020].iloc[0]
    assert year_row["rows"] == 2
    assert year_row["symbols"] == 2
    missing = result[result["missing_years"].notna()].iloc[0]
    assert missing["missing_years"] == "2019,2021"


def test_audit_detects_duplicate_keys(tmp_path):
    root = tmp_path / "rqdata"
    dataset = root / "prices_1d_pre"
    dataset.mkdir(parents=True)
    pd.DataFrame(
        {
            "trade_date": ["2020-01-02", "2020-01-02"],
            "order_book_id": ["AAA.X", "AAA.X"],
            "adjust_type": ["pre", "pre"],
        }
    ).to_parquet(dataset / "year=2020.parquet", index=False)

    result = audit_data_lake(data_root=root, datasets=["prices_1d_pre"], expected_start_year=2020, expected_end_year=2020)

    assert result.iloc[0]["duplicate_keys"] == 1
