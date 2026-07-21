import pandas as pd

from rq_platform.etl.hxz_p2_factors import (
    PORTFOLIO_IDS,
    assign_portfolios,
    build_hxz_factors,
    compute_breakpoints,
    compute_factors,
    compute_market_factor,
    compute_portfolio_returns,
    compute_style_factors,
)


def _demo_panel():
    rows = []
    idx = 1
    for size, cap in [("S", 100.0), ("B", 1000.0)]:
        for ia_label, ia in [("L", -0.20), ("M", 0.10), ("H", 0.50)]:
            for roe_label, roe in [("L", 0.01), ("M", 0.10), ("H", 0.30)]:
                rows.append(
                    {
                        "month": "2025-07",
                        "order_book_id": f"{idx:06d}.XSHE",
                        "monthly_return": 0.01 * idx,
                        "market_cap_lag": cap,
                        "float_market_cap_lag": cap * 0.8,
                        "june_market_cap": cap,
                        "ia": ia,
                        "roe": roe,
                        "size_formation_year": 2025,
                        "eligible_hxz_academic": True,
                        "is_common_a_share": True,
                        "is_listed": True,
                        "has_valid_return": True,
                        "has_valid_market_cap": True,
                        "is_financial": False,
                        "rf_monthly": 0.001,
                        "rf_monthly_1_over_12": 0.0011,
                        "listed_date": "2020-01-01",
                        "formation_date": "2025-07-01",
                        "previous_month_end_date": "2025-06-30",
                        "roe_info_date": "2025-04-20",
                        "is_st": False,
                        "is_suspended": False,
                        "trading_days_in_month": 22,
                    }
                )
                idx += 1
    rows.append(
        {
            "month": "2025-07",
            "order_book_id": "999999.XSHE",
            "monthly_return": 0.10,
            "market_cap_lag": 5000.0,
            "float_market_cap_lag": 4000.0,
            "june_market_cap": 5000.0,
            "ia": 0.2,
            "roe": 0.2,
            "size_formation_year": 2025,
            "eligible_hxz_academic": False,
            "is_common_a_share": True,
            "is_listed": True,
            "has_valid_return": True,
            "has_valid_market_cap": True,
            "is_financial": True,
            "rf_monthly": 0.001,
            "rf_monthly_1_over_12": 0.0011,
            "listed_date": "1991-04-03",
            "formation_date": "2025-07-01",
            "previous_month_end_date": "2025-06-30",
            "roe_info_date": "2025-04-20",
            "is_st": False,
            "is_suspended": False,
            "trading_days_in_month": 22,
        }
    )
    return pd.DataFrame(rows)


def test_breakpoints_and_30_40_30_sorts():
    panel = _demo_panel()
    breakpoints = compute_breakpoints(panel)

    annual = breakpoints[breakpoints["breakpoint_type"].eq("annual_size_ia")].iloc[0]
    monthly = breakpoints[breakpoints["breakpoint_type"].eq("monthly_roe")].iloc[0]

    assert annual["size_breakpoint"] == 550.0
    assert annual["size_effective_start"] == "2025-07"
    assert annual["size_effective_end"] == "2026-06"
    assert annual["ia_breakpoint_q30"] < annual["ia_breakpoint_q70"]
    assert monthly["roe_breakpoint_q30"] < monthly["roe_breakpoint_q70"]


def test_assignments_have_18_portfolios_and_weights_sum_to_one():
    panel = _demo_panel()
    assignments = assign_portfolios(panel, compute_breakpoints(panel))

    assert set(assignments["portfolio_id"]) == set(PORTFOLIO_IDS)
    assert assignments.duplicated(["month", "order_book_id"]).sum() == 0
    sums = assignments.groupby(["month", "portfolio_id"])["portfolio_weight"].sum()
    assert ((sums - 1).abs() < 1e-12).all()


def test_portfolio_return_recomputes_from_stock_weights():
    panel = _demo_panel()
    assignments = assign_portfolios(panel, compute_breakpoints(panel))
    returns, _ = compute_portfolio_returns(assignments, "market_cap_lag")

    recomputed = assignments.assign(wr=assignments["portfolio_weight"] * assignments["monthly_return"]).groupby(
        ["month", "portfolio_id"]
    )["wr"].sum()
    reported = returns.set_index(["month", "portfolio_id"])["portfolio_return"]

    assert ((recomputed - reported).abs() < 1e-12).all()


def test_factor_directions_are_small_big_low_high_and_high_low():
    rows = []
    for pid in PORTFOLIO_IDS:
        size, ia, roe = pid.split("_")
        value = 0.0
        value += 0.10 if size == "S" else 0.01
        value += 0.05 if ia == "L" else (-0.05 if ia == "H" else 0.0)
        value += 0.07 if roe == "H" else (-0.02 if roe == "L" else 0.0)
        rows.append({"month": "2025-07", "portfolio_id": pid, "weighted_return": value})
    factors = compute_style_factors(pd.DataFrame(rows), prefix="")

    assert factors.iloc[0]["R_ME"] > 0
    assert factors.iloc[0]["R_IA"] > 0
    assert factors.iloc[0]["R_ROE"] > 0


def test_mkt_includes_financial_stock_and_subtracts_rf():
    panel = _demo_panel()
    market = compute_market_factor(panel)

    assert market.iloc[0]["market_financial_stock_count"] == 1
    assert round(float(market.iloc[0]["MKT"]), 12) == round(float(market.iloc[0]["market_return"] - market.iloc[0]["rf_monthly"]), 12)


def test_missing_portfolio_sets_style_factors_missing():
    rows = [{"month": "2025-07", "portfolio_id": pid, "weighted_return": 0.01} for pid in PORTFOLIO_IDS[:-1]]

    factors = compute_style_factors(pd.DataFrame(rows), prefix="")

    assert pd.isna(factors.iloc[0]["R_ME"])
    assert "B_H_H" in factors.iloc[0]["missing_portfolios"]


def test_build_hxz_factors_is_idempotent(tmp_path):
    panel = _demo_panel()
    panel_path = tmp_path / "panel.parquet"
    panel.to_parquet(panel_path, index=False)
    output = tmp_path / "out"
    reports = tmp_path / "reports"

    first = build_hxz_factors(panel_path=panel_path, output_dir=output, report_dir=reports, start_month="2025-07")
    second = build_hxz_factors(panel_path=panel_path, output_dir=output, report_dir=reports, start_month="2025-07")

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert first["rows"]["assignments"] == second["rows"]["assignments"] == 18
    assert (output / "cn_hxz_4_factors_monthly.parquet").exists()
    assert (reports / "hxz_p2_factor_construction.md").exists()
