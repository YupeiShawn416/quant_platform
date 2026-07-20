import pandas as pd
from rq_platform.etl.hxz_p0_backfill import (
    DATASETS,
    build_hxz_p0_plan,
    load_hxz_status,
    run_hxz_p0_smoke,
    write_planned_status,
)
from rq_platform.etl.hxz_p0_quality import (
    check_financial_factor_daily_pit,
    check_financial_pit_quarterly,
    check_risk_free_rate,
)


def _write_demo_lake(root):
    (root / "instruments").mkdir(parents=True)
    pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "600519.XSHG", "300750.XSHE"],
            "type": ["CS", "CS", "CS"],
        }
    ).to_parquet(root / "instruments" / "instruments.parquet", index=False)
    (root / "trading_calendar").mkdir()
    pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-03", "2025-01-04", "2025-01-06"],
            "is_open": [True, True, False, True],
        }
    ).to_parquet(root / "trading_calendar" / "trading_calendar.parquet", index=False)
    (root / "prices_1d_none").mkdir()
    pd.DataFrame({"trade_date": ["2025-01-06"]}).to_parquet(
        root / "prices_1d_none" / "year=2025.parquet", index=False
    )


def test_hxz_p0_dry_run_is_deterministic_and_writes_no_formal_parquet(tmp_path):
    root = tmp_path / "rqdata"
    _write_demo_lake(root)

    plan1 = build_hxz_p0_plan(
        data_root=root,
        start_date="2025-01-02",
        end_date="2025-01-06",
        start_quarter="2024q3",
        end_quarter="2024q4",
        symbol_batch_size=2,
        date_chunk_size=2,
        quarter_chunk_size=1,
    )
    plan2 = build_hxz_p0_plan(
        data_root=root,
        start_date="2025-01-02",
        end_date="2025-01-06",
        start_quarter="2024q3",
        end_quarter="2024q4",
        symbol_batch_size=2,
        date_chunk_size=2,
        quarter_chunk_size=1,
    )

    assert [item["dataset"] for item in plan1["datasets"]] == DATASETS
    assert plan1["summary"]["symbols"] == 3
    assert plan1["summary"]["trading_dates"] == 3
    assert plan1["summary"]["quarters"] == 2
    assert plan1["summary"]["total_estimated_rows"] == plan2["summary"]["total_estimated_rows"]
    assert not list(root.glob("financial_*/*.parquet"))
    assert not list(root.glob("risk_free_rate/*.parquet"))


def test_hxz_status_log_schema_and_resume(tmp_path):
    root = tmp_path / "rqdata"
    _write_demo_lake(root)
    plan = build_hxz_p0_plan(data_root=root, end_date="2025-01-06")
    path = write_planned_status(plan, tmp_path / "status.csv")
    status = load_hxz_status(path)

    assert len(status) == 3
    assert set(status["status"]) == {"planned"}
    assert {"run_id", "dataset", "mode", "checksum"}.issubset(status.columns)


def test_hxz_smoke_without_key_is_blocked_and_isolated(tmp_path, monkeypatch):
    monkeypatch.delenv("RQDATAC_KEY", raising=False)
    monkeypatch.setattr("rq_platform.settings.settings.rqdata_license", None)

    result = run_hxz_p0_smoke(output_dir=tmp_path)

    assert result["status"] == "blocked"
    assert result["rqdata_calls"] == 0
    assert (tmp_path / "hxz_p0_smoke_validation.md").exists()
    assert not list(tmp_path.rglob("*.parquet"))


def test_financial_pit_quality_detects_duplicate_versions():
    frame = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "quarter": ["2024q3", "2024q3"],
            "info_date": ["2024-10-19", "2024-10-19"],
            "rice_create_tm": ["2024-10-18 20:00:00", "2024-10-18 20:00:00"],
            "if_adjusted": [0, 0],
            "total_assets": [1.0, 1.0],
            "equity_parent_company": [1.0, 1.0],
            "total_equity": [1.0, 1.0],
            "net_profit_parent_company": [1.0, 1.0],
        }
    )

    issues = check_financial_pit_quarterly(frame)

    assert any(issue.check == "candidate_key_unique" for issue in issues)


def test_financial_factor_quality_detects_duplicate_key():
    frame = pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-02"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "total_assets_mrq_0": [1.0, 1.0],
            "total_assets_lyr_0": [1.0, 1.0],
            "equity_parent_company_mrq_0": [1.0, 1.0],
            "equity_parent_company_lyr_0": [1.0, 1.0],
            "total_equity_mrq_0": [1.0, 1.0],
            "net_profit_parent_company_mrq_0": [1.0, 1.0],
            "net_profit_parent_company_lyr_0": [1.0, 1.0],
        }
    )

    issues = check_financial_factor_daily_pit(frame)

    assert any(issue.check == "primary_key_unique" for issue in issues)


def test_risk_free_quality_uses_decimal_rate_range():
    good = pd.DataFrame({"trade_date": ["2025-01-02"], "0S": [0.005], "1M": [0.01], "3M": [0.011], "1Y": [0.012]})
    bad = pd.DataFrame({"trade_date": ["2025-01-02"], "0S": [5.0], "1M": [0.01], "3M": [0.011], "1Y": [0.012]})

    assert check_risk_free_rate(good) == []
    assert any(issue.check == "0S_reasonable_range" for issue in check_risk_free_rate(bad))

