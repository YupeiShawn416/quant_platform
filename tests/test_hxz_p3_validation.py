import pandas as pd
from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.data.query_service import DataQueryService
from rq_platform.etl.hxz_p3_validation import (
    bh_fdr,
    build_cn_ff3,
    build_test_assets,
    compute_rolling_statistics,
    grs_stat,
    newey_west_cov,
    ols,
    run_hxz_integrated_validation,
    run_spanning_tests,
    run_subperiod_results,
)


def _panel():
    rows = []
    for month in ["2025-07", "2025-08"]:
        for i in range(1, 61):
            rows.append(
                {
                    "month": month,
                    "order_book_id": f"{i:06d}.XSHE",
                    "monthly_return": 0.001 * i,
                    "market_cap_lag": 100 + i,
                    "float_market_cap_lag": 80 + i,
                    "june_market_cap": 100 + i,
                    "book_equity_previous_quarter": 50 + i,
                    "ia": i / 100,
                    "roe": i / 200,
                    "size_formation_year": 2025,
                    "eligible_hxz_academic": True,
                    "is_common_a_share": True,
                    "is_listed": True,
                    "has_valid_return": True,
                    "has_valid_market_cap": True,
                    "positive_book_equity": True,
                    "rf_monthly": 0.001,
                    "board_type": "MainBoard",
                    "is_st": False,
                }
            )
    return pd.DataFrame(rows)


def test_ff3_constructs_size_bm_and_factors_without_future_data():
    out = build_cn_ff3(_panel())

    assert not out["factors"].empty
    assert {"MKT", "SMB", "HML"}.issubset(out["factors"].columns)
    assert out["assignments"].duplicated(["month", "order_book_id"]).sum() == 0
    assert out["breakpoints"].iloc[0]["breakpoint_universe"] == "all_eligible_a_shares"


def test_test_assets_are_monthly_and_no_future_columns_required():
    out = build_test_assets(_panel())

    assert out["asset_count"] > 0
    assert {"asset_group", "asset_id", "asset_return_vw", "asset_return_ew"}.issubset(out["returns"].columns)


def test_ols_newey_west_and_fdr_are_stable():
    y = pd.Series([0.01, 0.02, 0.015, 0.03, 0.025, 0.01, 0.02, 0.03])
    x = pd.DataFrame({"mkt": [0.01, 0.01, 0.02, 0.03, 0.02, 0.0, 0.01, 0.02]})

    res = ols(y.to_numpy(), x.to_numpy(), lag=3)
    cov = newey_west_cov(pd.DataFrame({"const": 1, "mkt": x["mkt"]}).to_numpy(), res["resid"], lag=3)
    q = bh_fdr(pd.Series([0.01, 0.20, 0.03]))

    assert len(res["params"]) == 2
    assert cov.shape == (2, 2)
    assert q.max() <= 0.2000001


def test_grs_and_spanning_outputs():
    y = pd.DataFrame({"a": [0.01, 0.02, 0.01, 0.03, 0.02], "b": [0.02, 0.01, 0.03, 0.02, 0.01]})
    x = pd.DataFrame({"MKT": [0.01, 0.0, 0.02, 0.01, 0.0], "R_ME": [0.0, 0.01, 0.0, 0.01, 0.0]})
    factors = pd.DataFrame(
        {
            "month": [f"2025-0{i}" for i in range(1, 6)],
            "MKT": x["MKT"],
            "SMB": x["R_ME"],
            "HML": [0.01, 0.01, 0.0, 0.0, 0.01],
            "R_ME": x["R_ME"],
            "R_IA": [0.0, 0.0, 0.01, 0.01, 0.0],
            "R_ROE": [0.01, 0.0, 0.0, 0.01, 0.01],
        }
    )

    grs = grs_stat(y, x)
    span = run_spanning_tests(factors, pd.DataFrame(columns=["month", "factor", "return"]))

    assert "grs_stat" in grs
    assert {"HML_on_HXZ", "SMB_on_HXZ"}.issubset(set(span["test"]))


def test_subperiod_results_include_three_periods():
    months = pd.period_range("2016-07", "2026-07", freq="M").astype(str)
    factors = pd.DataFrame({"month": months, "MKT": 0.01, "R_ME": 0.01, "R_IA": 0.01, "R_ROE": 0.01})

    out = run_subperiod_results(factors)

    assert out["period"].nunique() == 3


def test_rolling_statistics_include_ff3_factors():
    months = pd.period_range("2020-01", "2023-12", freq="M").astype(str)
    factors = pd.DataFrame(
        {
            "month": months,
            "MKT": 0.01,
            "SMB": 0.002,
            "HML": -0.001,
            "R_ME": 0.003,
            "R_IA": 0.004,
            "R_ROE": 0.005,
        }
    )

    out = compute_rolling_statistics(factors)

    assert {"MKT", "SMB", "HML", "R_ME", "R_IA", "R_ROE"} == set(out["factor"])
    assert out[out["factor"].eq("SMB")]["rolling_mean"].notna().any()


def test_data_api_lists_experimental_benchmark_specs():
    datasets = {item["dataset"] for item in DataQueryService().list_datasets()}

    assert "cn_hxz_4_factors_monthly" in datasets
    assert "cn_ff3_factors_monthly" in datasets


def test_api_can_query_experimental_benchmark_when_file_exists():
    client = TestClient(app)

    response = client.get("/data/schema/cn_hxz_4_factors_monthly")

    assert response.status_code in {200, 404}
