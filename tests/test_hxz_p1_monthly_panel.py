import pandas as pd

from rq_platform.etl.hxz_p1_monthly_panel import (
    build_hxz_monthly_research_panel,
    build_monthly_calendar,
    check_hxz_monthly_panel,
    compute_roe_from_selected,
    compute_monthly_rf,
    compute_monthly_returns,
    compute_monthly_annual_ia,
    derive_single_quarter_profit,
    next_quarter,
    select_pit_asof,
)


def _write(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_pit_asof_uses_weekend_before_monday_and_blocks_same_day():
    financials = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "000001.XSHE", "000001.XSHE"],
            "quarter": ["2024q4", "2024q4", "2024q4"],
            "info_date": ["2025-01-05", "2025-01-06", "2025-01-04"],
            "rice_create_tm": ["2025-01-05 20:00:00", "2025-01-06 08:00:00", "2025-01-04 20:00:00"],
            "if_adjusted": [0, 1, 0],
            "total_assets": [120.0, 130.0, 110.0],
            "equity_parent_company": [50.0, 51.0, 49.0],
            "total_equity": [52.0, 53.0, 50.0],
            "net_profit_parent_company": [12.0, 13.0, 11.0],
        }
    )

    selected = select_pit_asof(financials, "2025-01-06")

    assert len(selected) == 1
    assert selected.iloc[0]["selected_info_date"] == "2025-01-05"
    assert selected.iloc[0]["total_assets"] == 120.0
    assert selected.iloc[0]["version_count_available"] == 2


def test_multi_version_selection_chooses_latest_visible_version():
    financials = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "quarter": ["2024q3", "2024q3"],
            "info_date": ["2024-10-20", "2024-11-01"],
            "rice_create_tm": ["2024-10-20 20:00:00", "2024-11-01 20:00:00"],
            "if_adjusted": [0, 1],
            "total_assets": [100.0, 105.0],
            "equity_parent_company": [40.0, 41.0],
            "total_equity": [42.0, 43.0],
            "net_profit_parent_company": [9.0, 10.0],
        }
    )

    selected = select_pit_asof(financials, "2024-12-02")

    assert selected.iloc[0]["selected_info_date"] == "2024-11-01"
    assert selected.iloc[0]["selected_if_adjusted"] == 1


def test_single_quarter_profit_conversion_q1_q2_q3_q4_and_missing_previous():
    selected = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE"] * 4 + ["600000.XSHG"],
            "quarter": ["2024q1", "2024q2", "2024q3", "2024q4", "2024q3"],
            "net_profit_parent_company": [10.0, 25.0, 33.0, 50.0, 9.0],
        }
    )

    out = derive_single_quarter_profit(selected)
    values = out[out["order_book_id"].eq("000001.XSHE")].set_index("quarter")["single_quarter_parent_profit"].to_dict()

    assert values == {"2024q1": 10.0, "2024q2": 15.0, "2024q3": 8.0, "2024q4": 17.0}
    assert out[out["order_book_id"].eq("600000.XSHG")].iloc[0]["single_quarter_conversion_status"] == "missing_previous_cumulative"


def test_roe_uses_previous_quarter_equity_and_marks_stale():
    selected = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "quarter": ["2024q1", "2024q2"],
            "selected_info_date": ["2024-04-20", "2024-08-20"],
            "selected_rice_create_tm": ["2024-04-20 20:00:00", "2024-08-20 20:00:00"],
            "selected_if_adjusted": [0, 0],
            "version_count_available": [1, 1],
            "net_profit_parent_company": [10.0, 25.0],
            "equity_parent_company": [100.0, 120.0],
            "total_equity": [110.0, 130.0],
        }
    )

    roe = compute_roe_from_selected(selected, "2024-09-02", "2024-09")
    q2 = roe[roe["quarter"].eq("2024q2")].iloc[0]

    assert q2["single_quarter_parent_profit"] == 15.0
    assert q2["book_equity_previous_quarter"] == 100.0
    assert round(float(q2["roe"]), 6) == 0.15
    assert q2["roe_is_stale"] is False or q2["roe_is_stale"] == False


def test_roe_six_month_stale_flag():
    selected = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE"],
            "quarter": ["2024q1"],
            "selected_info_date": ["2024-04-20"],
            "selected_rice_create_tm": ["2024-04-20 20:00:00"],
            "selected_if_adjusted": [0],
            "version_count_available": [1],
            "net_profit_parent_company": [10.0],
            "equity_parent_company": [100.0],
            "total_equity": [110.0],
        }
    )

    roe = compute_roe_from_selected(selected, "2024-12-02", "2024-12")

    assert roe.iloc[0]["roe_is_stale"] is True or roe.iloc[0]["roe_is_stale"] == True
    assert roe.iloc[0]["has_valid_roe"] is False or roe.iloc[0]["has_valid_roe"] == False


def test_annual_ia_uses_consecutive_q4_assets_with_july_effective_year():
    financials = pd.DataFrame(
        {
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "quarter": ["2023q4", "2024q4"],
            "info_date": ["2024-03-20", "2025-03-20"],
            "rice_create_tm": ["2024-03-20 20:00:00", "2025-03-20 20:00:00"],
            "if_adjusted": [0, 0],
            "total_assets": [100.0, 130.0],
            "equity_parent_company": [50.0, 60.0],
            "total_equity": [52.0, 62.0],
            "net_profit_parent_company": [10.0, 12.0],
        }
    )
    monthly_calendar = pd.DataFrame({"month": ["2025-07"], "formation_date": ["2025-07-01"]})

    ia = compute_monthly_annual_ia(financials, monthly_calendar)

    assert ia.iloc[0]["current_fy"] == 2024
    assert ia.iloc[0]["prior_fy"] == 2023
    assert round(float(ia.iloc[0]["ia"]), 6) == 0.3
    assert ia.iloc[0]["ia_effective_start"] == "2025-07"
    assert ia.iloc[0]["ia_effective_end"] == "2026-06"


def test_monthly_return_uses_pre_adjusted_previous_month_end_close():
    calendar = pd.DataFrame(
        {
            "month": ["2025-01"],
            "formation_date": ["2025-01-02"],
            "month_end_date": ["2025-01-31"],
            "previous_month_end_date": ["2024-12-31"],
            "expected_trading_days": [2],
        }
    )
    prices = pd.DataFrame(
        {
            "trade_date": ["2024-12-31", "2025-01-02", "2025-01-31"],
            "order_book_id": ["000001.XSHE", "000001.XSHE", "000001.XSHE"],
            "close": [10.0, 11.0, 12.0],
        }
    )

    returns = compute_monthly_returns(prices, calendar)

    assert round(float(returns.iloc[0]["monthly_return"]), 6) == 0.2
    assert returns.iloc[0]["trading_days_in_month"] == 2
    assert returns.iloc[0]["return_valid"] is True or returns.iloc[0]["return_valid"] == True


def test_rf_annual_to_monthly_uses_latest_before_formation():
    calendar = pd.DataFrame(
        {
            "month": ["2025-01"],
            "formation_date": ["2025-01-02"],
            "holding_calendar_days": [30],
        }
    )
    rf = pd.DataFrame({"trade_date": ["2025-01-01", "2025-01-02"], "1M": [0.012, 0.02]})

    monthly = compute_monthly_rf(rf, calendar)

    assert monthly.iloc[0]["rf_source_date"] == "2025-01-01"
    assert round(float(monthly.iloc[0]["rf_monthly"]), 8) == round((1.012) ** (30 / 365) - 1, 8)
    assert round(float(monthly.iloc[0]["rf_monthly_1_over_12"]), 8) == round((1.012) ** (1 / 12) - 1, 8)


def test_monthly_calendar_uses_first_trade_previous_trade_and_month_end():
    calendar = pd.DataFrame(
        {
            "trade_date": ["2024-12-31", "2025-01-01", "2025-01-02", "2025-01-31", "2025-02-03"],
            "is_open": [True, False, True, True, True],
        }
    )

    monthly = build_monthly_calendar(calendar, start_month="2025-01", end_month="2025-01")

    assert monthly.iloc[0]["formation_date"] == "2025-01-02"
    assert monthly.iloc[0]["previous_trade_date"] == "2024-12-31"
    assert monthly.iloc[0]["month_end_date"] == "2025-01-31"
    assert monthly.iloc[0]["previous_month_end_date"] == "2024-12-31"


def test_quality_detects_primary_key_and_no_lookahead_violations():
    panel = pd.DataFrame(
        {
            "month": ["2025-01", "2025-01"],
            "order_book_id": ["000001.XSHE", "000001.XSHE"],
            "formation_date": ["2025-01-02", "2025-01-02"],
            "roe_info_date": ["2025-01-02", "2025-01-01"],
            "current_assets_info_date": ["2025-01-01", "2025-01-01"],
            "prior_assets_info_date": ["2025-01-01", "2025-01-01"],
            "has_valid_roe": [True, True],
            "roe_is_stale": [False, False],
            "monthly_return": [0.1, 0.1],
            "market_cap_date": ["2024-12-31", "2024-12-31"],
            "previous_month_end_date": ["2024-12-31", "2024-12-31"],
        }
    )
    monthly_calendar = pd.DataFrame({"month": ["2025-01"]})

    quality = check_hxz_monthly_panel(panel, monthly_calendar, pd.DataFrame(), pd.DataFrame())

    assert quality["duplicate_key"] == 1
    assert quality["no_lookahead_violations"] == 1
    assert quality["error_count"] >= 2


def test_next_quarter_rolls_year():
    assert next_quarter("2024q3") == "2024q4"
    assert next_quarter("2024q4") == "2025q1"


def test_build_monthly_panel_is_idempotent_on_small_lake(tmp_path):
    root = tmp_path / "rqdata"
    _write(
        root / "trading_calendar" / "trading_calendar.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2024-12-31", "2025-01-02", "2025-01-31"],
                "is_open": [True, True, True],
            }
        ),
    )
    _write(
        root / "instruments" / "instruments.parquet",
        pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE"],
                "type": ["CS"],
                "listed_date": ["2020-01-01"],
                "de_listed_date": [None],
                "status": ["Active"],
                "special_type": ["Normal"],
                "sector_code_name": ["工业"],
                "sector_code": ["Industrials"],
                "board_type": ["MainBoard"],
            }
        ),
    )
    _write(
        root / "prices_1d_pre" / "year=2024.parquet",
        pd.DataFrame({"trade_date": ["2024-12-31"], "order_book_id": ["000001.XSHE"], "close": [10.0]}),
    )
    _write(
        root / "prices_1d_pre" / "year=2025.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2025-01-02", "2025-01-31"],
                "order_book_id": ["000001.XSHE", "000001.XSHE"],
                "close": [10.5, 12.0],
            }
        ),
    )
    _write(
        root / "valuation_1d" / "year=2024.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2024-12-31"],
                "order_book_id": ["000001.XSHE"],
                "market_cap": [100.0],
                "float_market_cap": [80.0],
            }
        ),
    )
    _write(
        root / "valuation_1d" / "year=2025.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2025-01-31"],
                "order_book_id": ["000001.XSHE"],
                "market_cap": [120.0],
                "float_market_cap": [90.0],
            }
        ),
    )
    _write(
        root / "tradability_1d" / "year=2025.parquet",
        pd.DataFrame(
            {
                "trade_date": ["2025-01-02"],
                "order_book_id": ["000001.XSHE"],
                "is_listed": [True],
                "is_suspended": [False],
                "is_st": [False],
                "can_buy": [True],
                "can_sell": [True],
            }
        ),
    )
    _write(
        root / "industry_classification" / "year=2025.parquet",
        pd.DataFrame({"trade_date": ["2025-01-02"], "order_book_id": ["000001.XSHE"], "industry_code": ["10"], "industry_name": ["制造"]}),
    )
    _write(
        root / "risk_free_rate" / "year=2024.parquet",
        pd.DataFrame({"trade_date": ["2024-12-31"], "0S": [0.01], "1M": [0.012], "3M": [0.013], "1Y": [0.014]}),
    )
    _write(
        root / "financial_pit_quarterly" / "year=2024.parquet",
        pd.DataFrame(
            {
                "order_book_id": ["000001.XSHE"] * 5,
                "quarter": ["2022q4", "2023q4", "2024q1", "2024q2", "2024q3"],
                "info_date": ["2023-03-20", "2024-03-20", "2024-04-20", "2024-08-20", "2024-10-20"],
                "rice_create_tm": [
                    "2023-03-20 20:00:00",
                    "2024-03-20 20:00:00",
                    "2024-04-20 20:00:00",
                    "2024-08-20 20:00:00",
                    "2024-10-20 20:00:00",
                ],
                "if_adjusted": [0, 0, 0, 0, 0],
                "total_assets": [90.0, 100.0, 105.0, 110.0, 115.0],
                "equity_parent_company": [40.0, 50.0, 52.0, 54.0, 56.0],
                "total_equity": [42.0, 52.0, 54.0, 56.0, 58.0],
                "net_profit_parent_company": [8.0, 10.0, 3.0, 7.0, 9.0],
            }
        ),
    )

    first = build_hxz_monthly_research_panel(data_root=root, start_month="2025-01", end_month="2025-01", report_dir=tmp_path / "reports")
    second = build_hxz_monthly_research_panel(data_root=root, start_month="2025-01", end_month="2025-01", report_dir=tmp_path / "reports")
    panel = pd.read_parquet(root / "derived" / "hxz_monthly_panel" / "hxz_monthly_research_panel.parquet")

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert first["rows"] == second["rows"] == 1
    assert len(panel) == 1
    assert panel.iloc[0]["market_cap_date"] == "2024-12-31"
    assert panel.iloc[0]["eligible_hxz_academic"] is True or panel.iloc[0]["eligible_hxz_academic"] == True
