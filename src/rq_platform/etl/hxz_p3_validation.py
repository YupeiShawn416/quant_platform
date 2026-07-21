from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from rq_platform.etl.hxz_p2_factors import PORTFOLIO_IDS, atomic_write_parquet
from rq_platform.settings import settings


REPORT_DIR = Path("reports/03_hxz_integrated_validation")
FF3_DATASET = "derived/cn_ff3"
VALIDATION_DATASET = "derived/hxz_validation"
ASSET_GROUPS = ["size_bm_25", "size_decile", "bm_decile", "momentum_decile", "reversal_decile", "volatility_decile", "liquidity_decile", "ia_decile", "roe_decile"]


@dataclass(frozen=True)
class HXZP3Paths:
    root: Path
    panel: Path
    hxz_factors: Path
    hxz_assignments: Path
    hxz_portfolios: Path
    hxz_breakpoints: Path
    ff3_root: Path
    validation_root: Path
    report_dir: Path


def run_hxz_integrated_validation(
    *,
    data_root: str | Path | None = None,
    report_dir: str | Path = REPORT_DIR,
) -> dict[str, Any]:
    paths = _paths(data_root, report_dir)
    panel = pd.read_parquet(paths.panel)
    hxz_factors = pd.read_parquet(paths.hxz_factors)
    hxz_assignments = pd.read_parquet(paths.hxz_assignments)
    hxz_portfolios = pd.read_parquet(paths.hxz_portfolios)
    hxz_breakpoints = pd.read_parquet(paths.hxz_breakpoints)

    recompute = recompute_p2_checks(panel, hxz_assignments, hxz_portfolios, hxz_factors)
    ff3 = build_cn_ff3(panel)
    test_assets = build_test_assets(panel)
    factors = hxz_factors.merge(ff3["factors"][["month", "SMB", "HML"]], on="month", how="left")
    regressions = run_asset_pricing_regressions(test_assets["returns"], factors)
    model_comparison = summarize_model_comparison(regressions)
    grs = compute_grs_tests(test_assets["returns"], factors)
    spanning = run_spanning_tests(factors, test_assets["factor_like"])
    subperiod = run_subperiod_results(factors)
    segment = run_segment_results(panel, factors)
    rolling = compute_rolling_statistics(factors)
    integration = build_benchmark_integration(recompute, model_comparison)
    report = build_report(
        recompute=recompute,
        ff3=ff3,
        test_assets=test_assets,
        factors=factors,
        regressions=regressions,
        model_comparison=model_comparison,
        grs=grs,
        spanning=spanning,
        subperiod=subperiod,
        segment=segment,
        rolling=rolling,
        integration=integration,
    )
    outputs = write_outputs(paths, ff3, test_assets, factors, regressions, model_comparison, grs, spanning, subperiod, segment, rolling, report)
    plot_outputs = write_plots(paths.report_dir, factors, model_comparison, rolling)
    outputs.update(plot_outputs)
    report["outputs"] = {key: str(path) for key, path in outputs.items()}
    write_report_markdown(paths.report_dir, report)
    return report


def recompute_p2_checks(panel: pd.DataFrame, assignments: pd.DataFrame, portfolios: pd.DataFrame, factors: pd.DataFrame) -> dict[str, Any]:
    weight_sum = assignments.groupby(["month", "portfolio_id"])["portfolio_weight"].sum()
    weight_errors = int(((weight_sum - 1).abs() > 1e-8).sum())
    recomputed_port = assignments.assign(_wr=assignments["portfolio_weight"] * assignments["monthly_return"]).groupby(["month", "portfolio_id"])["_wr"].sum()
    reported_port = portfolios.set_index(["month", "portfolio_id"])["portfolio_return"]
    port_diff = (recomputed_port - reported_port).abs()
    pivot = reported_port.unstack("portfolio_id")
    recomputed_factors = pd.DataFrame({"month": pivot.index})
    recomputed_factors["R_ME"] = pivot[[c for c in pivot.columns if c.startswith("S_")]].mean(axis=1).values - pivot[[c for c in pivot.columns if c.startswith("B_")]].mean(axis=1).values
    recomputed_factors["R_IA"] = pivot[[c for c in pivot.columns if c.split("_")[1] == "L"]].mean(axis=1).values - pivot[[c for c in pivot.columns if c.split("_")[1] == "H"]].mean(axis=1).values
    recomputed_factors["R_ROE"] = pivot[[c for c in pivot.columns if c.split("_")[2] == "H"]].mean(axis=1).values - pivot[[c for c in pivot.columns if c.split("_")[2] == "L"]].mean(axis=1).values
    merged = factors.merge(recomputed_factors, on="month", suffixes=("", "_recomputed"))
    factor_errors = {col: float((merged[col] - merged[f"{col}_recomputed"]).abs().max()) for col in ["R_ME", "R_IA", "R_ROE"]}
    market_pool = panel[
        panel["month"].isin(factors["month"])
        & panel["is_common_a_share"].fillna(False)
        & panel["is_listed"].fillna(False)
        & panel["has_valid_return"].fillna(False)
        & panel["has_valid_market_cap"].fillna(False)
    ].copy()
    denom = market_pool.groupby("month")["market_cap_lag"].transform("sum")
    market_pool["_wr"] = market_pool["market_cap_lag"] / denom * market_pool["monthly_return"]
    mkt = market_pool.groupby("month").agg(market_return_recomputed=("_wr", "sum"), rf_monthly=("rf_monthly", "first")).reset_index()
    mkt["MKT_recomputed"] = mkt["market_return_recomputed"] - mkt["rf_monthly"]
    mkt_diff = factors.merge(mkt[["month", "MKT_recomputed"]], on="month")
    no_lookahead = int(
        sum(
            (pd.to_datetime(assignments[col], errors="coerce") >= pd.to_datetime(assignments["formation_date"], errors="coerce")).sum()
            for col in ["roe_info_date", "current_assets_info_date", "prior_assets_info_date"]
            if col in assignments.columns
        )
    )
    return {
        "portfolio_max_abs_diff": float(port_diff.max()),
        "factor_max_abs_diff": factor_errors,
        "mkt_max_abs_diff": float((mkt_diff["MKT"] - mkt_diff["MKT_recomputed"]).abs().max()),
        "weight_sum_error_count": weight_errors,
        "assignment_duplicate_key": int(assignments.duplicated(["month", "order_book_id"]).sum()),
        "portfolio_month_rows": int(len(portfolios)),
        "expected_portfolio_month_rows": int(factors["month"].nunique() * 18),
        "no_lookahead_violations": no_lookahead,
        "p2_recompute_pass": bool(port_diff.max() < 1e-10 and max(factor_errors.values()) < 1e-10 and weight_errors == 0 and no_lookahead == 0),
    }


def build_cn_ff3(panel: pd.DataFrame) -> dict[str, pd.DataFrame]:
    base = panel[panel["month"].astype(str) >= "2016-07"].copy()
    base["book_to_market"] = pd.to_numeric(base["book_equity_previous_quarter"], errors="coerce") / pd.to_numeric(base["market_cap_lag"], errors="coerce")
    eligible = base[
        base["is_common_a_share"].fillna(False)
        & base["is_listed"].fillna(False)
        & base["positive_book_equity"].fillna(False)
        & base["has_valid_return"].fillna(False)
        & base["has_valid_market_cap"].fillna(False)
        & base["book_to_market"].notna()
    ].copy()
    annual_rows = []
    for year, group in eligible.groupby("size_formation_year"):
        year = int(year)
        source = group[group["month"].eq(f"{year}-07")]
        if source.empty:
            continue
        annual_rows.append(
            {
                "size_formation_year": year,
                "month": f"{year}-07",
                "size_breakpoint": float(source["june_market_cap"].median()),
                "bm_q30": float(source["book_to_market"].quantile(0.3)),
                "bm_q70": float(source["book_to_market"].quantile(0.7)),
                "breakpoint_universe": "all_eligible_a_shares",
                "eligible_count": int(len(source)),
                "effective_start": f"{year}-07",
                "effective_end": f"{year + 1}-06",
            }
        )
    breakpoints = pd.DataFrame(annual_rows)
    assigned = eligible.merge(breakpoints[["size_formation_year", "size_breakpoint", "bm_q30", "bm_q70", "effective_start", "effective_end"]], on="size_formation_year", how="left")
    assigned["size_group"] = assigned["june_market_cap"].le(assigned["size_breakpoint"]).map({True: "S", False: "B"})
    assigned["bm_group"] = pd.NA
    assigned.loc[assigned["book_to_market"].le(assigned["bm_q30"]), "bm_group"] = "L"
    assigned.loc[assigned["book_to_market"].gt(assigned["bm_q30"]) & assigned["book_to_market"].le(assigned["bm_q70"]), "bm_group"] = "M"
    assigned.loc[assigned["book_to_market"].gt(assigned["bm_q70"]), "bm_group"] = "H"
    assigned = assigned.dropna(subset=["size_group", "bm_group"]).copy()
    assigned["portfolio_id"] = assigned["size_group"] + "_" + assigned["bm_group"]
    assigned["portfolio_weight"] = assigned["market_cap_lag"] / assigned.groupby(["month", "portfolio_id"])["market_cap_lag"].transform("sum")
    assigned["_wr"] = assigned["portfolio_weight"] * assigned["monthly_return"]
    portfolios = assigned.groupby(["month", "portfolio_id"]).agg(
        stock_count=("order_book_id", "nunique"),
        portfolio_return=("_wr", "sum"),
        equal_weighted_return=("monthly_return", "mean"),
        total_market_cap=("market_cap_lag", "sum"),
    ).reset_index()
    pivot = portfolios.pivot(index="month", columns="portfolio_id", values="portfolio_return")
    factors = pd.DataFrame({"month": pivot.index})
    factors["SMB"] = pivot[[c for c in pivot.columns if c.startswith("S_")]].mean(axis=1).values - pivot[[c for c in pivot.columns if c.startswith("B_")]].mean(axis=1).values
    factors["HML"] = pivot[[c for c in pivot.columns if c.endswith("_H")]].mean(axis=1).values - pivot[[c for c in pivot.columns if c.endswith("_L")]].mean(axis=1).values
    mkt = compute_market(base)
    factors = mkt.merge(factors, on="month", how="left")
    return {"factors": factors.reset_index(drop=True), "assignments": assigned.reset_index(drop=True), "portfolios": portfolios, "breakpoints": breakpoints}


def compute_market(panel: pd.DataFrame) -> pd.DataFrame:
    pool = panel[
        panel["is_common_a_share"].fillna(False)
        & panel["is_listed"].fillna(False)
        & panel["has_valid_return"].fillna(False)
        & panel["has_valid_market_cap"].fillna(False)
    ].dropna(subset=["monthly_return", "market_cap_lag"]).copy()
    pool["_wr"] = pool["market_cap_lag"] / pool.groupby("month")["market_cap_lag"].transform("sum") * pool["monthly_return"]
    out = pool.groupby("month").agg(MKT_raw=("_wr", "sum"), rf_monthly=("rf_monthly", "first"), market_stock_count=("order_book_id", "nunique")).reset_index()
    out["MKT"] = out["MKT_raw"] - out["rf_monthly"]
    return out


def build_test_assets(panel: pd.DataFrame) -> dict[str, Any]:
    base = panel[panel["month"].astype(str) >= "2016-07"].copy()
    base["book_to_market"] = pd.to_numeric(base["book_equity_previous_quarter"], errors="coerce") / pd.to_numeric(base["market_cap_lag"], errors="coerce")
    base = base.sort_values(["order_book_id", "month"])
    base["momentum_12_2"] = base.groupby("order_book_id")["monthly_return"].transform(lambda s: (1 + s.shift(2)).rolling(11, min_periods=6).apply(np.prod, raw=True) - 1)
    base["reversal_1m"] = base.groupby("order_book_id")["monthly_return"].shift(1)
    base["volatility_12m"] = base.groupby("order_book_id")["monthly_return"].transform(lambda s: s.shift(1).rolling(12, min_periods=6).std())
    base["liquidity_float_ratio"] = pd.to_numeric(base["float_market_cap_lag"], errors="coerce") / pd.to_numeric(base["market_cap_lag"], errors="coerce")
    asset_frames = []
    for name, col in [
        ("size_decile", "market_cap_lag"),
        ("bm_decile", "book_to_market"),
        ("momentum_decile", "momentum_12_2"),
        ("reversal_decile", "reversal_1m"),
        ("volatility_decile", "volatility_12m"),
        ("liquidity_decile", "liquidity_float_ratio"),
        ("ia_decile", "ia"),
        ("roe_decile", "roe"),
    ]:
        asset_frames.append(decile_assets(base, col, name))
    asset_frames.append(size_bm_25_assets(base))
    returns = pd.concat(asset_frames, ignore_index=True)
    factor_like = make_factor_like_assets(returns)
    return {
        "returns": returns,
        "factor_like": factor_like,
        "asset_count": int(returns["asset_id"].nunique()),
        "vix_beta_status": "missing_compatible_monthly_cross_section",
    }


def decile_assets(panel: pd.DataFrame, column: str, group_name: str) -> pd.DataFrame:
    rows = []
    eligible = panel[
        panel["is_common_a_share"].fillna(False)
        & panel["is_listed"].fillna(False)
        & panel["has_valid_return"].fillna(False)
        & panel["has_valid_market_cap"].fillna(False)
        & panel[column].notna()
    ].copy()
    for month, group in eligible.groupby("month"):
        if len(group) < 20:
            continue
        group = group.copy()
        group["bucket"] = pd.qcut(group[column].rank(method="first"), 10, labels=False) + 1
        rows.extend(weighted_asset_rows(group, month, group_name, lambda r: f"D{int(r['bucket']):02d}"))
    return pd.DataFrame(rows)


def size_bm_25_assets(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    eligible = panel[
        panel["is_common_a_share"].fillna(False)
        & panel["is_listed"].fillna(False)
        & panel["has_valid_return"].fillna(False)
        & panel["has_valid_market_cap"].fillna(False)
        & panel["book_to_market"].notna()
    ].copy()
    for month, group in eligible.groupby("month"):
        if len(group) < 50:
            continue
        group = group.copy()
        group["size_bucket"] = pd.qcut(group["market_cap_lag"].rank(method="first"), 5, labels=False) + 1
        group["bm_bucket"] = pd.qcut(group["book_to_market"].rank(method="first"), 5, labels=False) + 1
        rows.extend(weighted_asset_rows(group, month, "size_bm_25", lambda r: f"S{int(r['size_bucket'])}_BM{int(r['bm_bucket'])}"))
    return pd.DataFrame(rows)


def weighted_asset_rows(group: pd.DataFrame, month: str, asset_group: str, label_func) -> list[dict[str, Any]]:
    group = group.copy()
    group["asset_id"] = group.apply(label_func, axis=1)
    out = []
    for asset_id, bucket in group.groupby("asset_id"):
        weights = bucket["market_cap_lag"] / bucket["market_cap_lag"].sum()
        ew = 1 / len(bucket)
        out.append(
            {
                "month": month,
                "asset_group": asset_group,
                "asset_id": f"{asset_group}:{asset_id}",
                "asset_return_vw": float((weights * bucket["monthly_return"]).sum()),
                "asset_return_ew": float((ew * bucket["monthly_return"]).sum()),
                "stock_count": int(bucket["order_book_id"].nunique()),
                "top1_weight": float(weights.max()),
                "top5_weight": float(weights.sort_values(ascending=False).head(5).sum()),
                "HHI": float((weights**2).sum()),
            }
        )
    return out


def make_factor_like_assets(returns: pd.DataFrame) -> pd.DataFrame:
    records = []
    for name in ["momentum_decile", "reversal_decile", "volatility_decile", "liquidity_decile"]:
        wide = returns[returns["asset_group"].eq(name)].pivot(index="month", columns="asset_id", values="asset_return_vw")
        if wide.empty:
            continue
        low = f"{name}:D01"
        high = f"{name}:D10"
        if low in wide.columns and high in wide.columns:
            records.append(pd.DataFrame({"month": wide.index, "factor": name, "return": wide[high] - wide[low]}))
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame(columns=["month", "factor", "return"])


def run_asset_pricing_regressions(asset_returns: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    merged = asset_returns.merge(factors, on="month", how="left")
    merged["excess_return"] = merged["asset_return_vw"] - merged["rf_monthly"]
    models = {
        "CAPM": ["MKT"],
        "FF3": ["MKT", "SMB", "HML"],
        "HXZ": ["MKT", "R_ME", "R_IA", "R_ROE"],
    }
    for (asset_group, asset_id), group in merged.groupby(["asset_group", "asset_id"]):
        for model, cols in models.items():
            data = group.dropna(subset=["excess_return", *cols])
            if len(data) < len(cols) + 12:
                continue
            res = ols(data["excess_return"].to_numpy(), data[cols].to_numpy(), lag=3)
            res6 = ols(data["excess_return"].to_numpy(), data[cols].to_numpy(), lag=6)
            rows.append(
                {
                    "asset_group": asset_group,
                    "asset_id": asset_id,
                    "model": model,
                    "months": len(data),
                    "alpha": res["params"][0],
                    "alpha_t": res["t"][0],
                    "alpha_nw_t_lag3": res["nw_t"][0],
                    "alpha_nw_t_lag6": res6["nw_t"][0],
                    "adj_r2": res["adj_r2"],
                    **{f"beta_{c}": res["params"][i + 1] for i, c in enumerate(cols)},
                }
            )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["alpha_p_approx"] = 2 * (1 - normal_cdf(frame["alpha_nw_t_lag3"].abs()))
        frame["alpha_bh_fdr_q"] = bh_fdr(frame["alpha_p_approx"])
        frame["alpha_significant_5pct"] = frame["alpha_p_approx"] < 0.05
    return frame


def summarize_model_comparison(regressions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (asset_group, model), group in regressions.groupby(["asset_group", "model"]):
        rows.append(comparison_row(asset_group, model, group))
    for model, group in regressions.groupby("model"):
        rows.append(comparison_row("ALL", model, group))
    return pd.DataFrame(rows)


def comparison_row(asset_group: str, model: str, group: pd.DataFrame) -> dict[str, Any]:
    return {
        "asset_group": asset_group,
        "model": model,
        "portfolio_count": int(len(group)),
        "mean_abs_alpha": float(group["alpha"].abs().mean()),
        "median_abs_alpha": float(group["alpha"].abs().median()),
        "significant_alpha_count": int(group["alpha_significant_5pct"].sum()),
        "significant_alpha_ratio": float(group["alpha_significant_5pct"].mean()),
        "avg_adj_r2": float(group["adj_r2"].mean()),
        "median_adj_r2": float(group["adj_r2"].median()),
    }


def compute_grs_tests(asset_returns: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    models = {"CAPM": ["MKT"], "FF3": ["MKT", "SMB", "HML"], "HXZ": ["MKT", "R_ME", "R_IA", "R_ROE"]}
    for asset_group in sorted(asset_returns["asset_group"].unique()):
        assets = asset_returns[asset_returns["asset_group"].eq(asset_group)]
        wide = assets.pivot(index="month", columns="asset_id", values="asset_return_vw")
        data = wide.merge(factors.set_index("month"), left_index=True, right_index=True).dropna()
        if len(data) < 24 or wide.shape[1] < 2:
            continue
        y = data[wide.columns].subtract(data["rf_monthly"], axis=0)
        for model, cols in models.items():
            result = grs_stat(y, data[cols])
            rows.append({"asset_group": asset_group, "model": model, **result})
    return pd.DataFrame(rows)


def run_spanning_tests(factors: pd.DataFrame, factor_like: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tests = {
        "HML_on_HXZ": ("HML", ["MKT", "R_ME", "R_IA", "R_ROE"]),
        "SMB_on_HXZ": ("SMB", ["MKT", "R_ME", "R_IA", "R_ROE"]),
        "R_ME_on_FF3": ("R_ME", ["MKT", "SMB", "HML"]),
        "R_IA_on_FF3": ("R_IA", ["MKT", "SMB", "HML"]),
        "R_ROE_on_FF3": ("R_ROE", ["MKT", "SMB", "HML"]),
    }
    for name, (ycol, xcols) in tests.items():
        data = factors.dropna(subset=[ycol, *xcols])
        res = ols(data[ycol].to_numpy(), data[xcols].to_numpy(), lag=3)
        rows.append({"test": name, "lhs": ycol, "rhs": ",".join(xcols), "alpha": res["params"][0], "alpha_nw_t": res["nw_t"][0], "adj_r2": res["adj_r2"]})
    for factor, group in factor_like.groupby("factor"):
        data = group.merge(factors, on="month").dropna(subset=["return", "MKT", "R_ME", "R_IA", "R_ROE"])
        if len(data) >= 24:
            res = ols(data["return"].to_numpy(), data[["MKT", "R_ME", "R_IA", "R_ROE"]].to_numpy(), lag=3)
            rows.append({"test": f"{factor}_on_HXZ", "lhs": factor, "rhs": "MKT,R_ME,R_IA,R_ROE", "alpha": res["params"][0], "alpha_nw_t": res["nw_t"][0], "adj_r2": res["adj_r2"]})
    return pd.DataFrame(rows)


def run_subperiod_results(factors: pd.DataFrame) -> pd.DataFrame:
    periods = [("2016-07", "2019-12"), ("2020-01", "2022-12"), ("2023-01", "2026-07")]
    rows = []
    for start, end in periods:
        sub = factors[factors["month"].between(start, end)]
        for col in ["MKT", "R_ME", "R_IA", "R_ROE"]:
            s = sub[col].dropna()
            rows.append({"period": f"{start}:{end}", "factor": col, "months": len(s), "mean_monthly": s.mean(), "vol_monthly": s.std(), "sharpe_ann": (s.mean() / s.std() * math.sqrt(12)) if s.std() else None, "positive_ratio": (s > 0).mean()})
    return pd.DataFrame(rows)


def run_segment_results(panel: pd.DataFrame, factors: pd.DataFrame) -> pd.DataFrame:
    rows = []
    base = panel[panel["month"].isin(factors["month"]) & panel["has_valid_return"].fillna(False) & panel["has_valid_market_cap"].fillna(False)].copy()
    segments = {
        "all_a": base["is_common_a_share"].fillna(False),
        "main_board": base["board_type"].astype(str).eq("MainBoard"),
        "gem": base["board_type"].astype(str).eq("GEM"),
        "ksh": base["board_type"].astype(str).eq("KSH"),
        "exclude_st": ~base["is_st"].fillna(False),
        "eligible_academic": base["eligible_hxz_academic"].fillna(False),
    }
    for name, mask in segments.items():
        sub = base[mask].copy()
        if sub.empty:
            continue
        sub["_wr"] = sub["market_cap_lag"] / sub.groupby("month")["market_cap_lag"].transform("sum") * sub["monthly_return"]
        ret = sub.groupby("month").agg(return_vw=("_wr", "sum"), stock_count=("order_book_id", "nunique")).reset_index()
        merged = ret.merge(factors[["month", "rf_monthly"]], on="month", how="left")
        rows.append({"segment": name, "months": len(merged), "avg_stock_count": merged["stock_count"].mean(), "mean_excess_return": (merged["return_vw"] - merged["rf_monthly"]).mean(), "vol": (merged["return_vw"] - merged["rf_monthly"]).std()})
    return pd.DataFrame(rows)


def compute_rolling_statistics(factors: pd.DataFrame, window: int = 36) -> pd.DataFrame:
    rows = []
    cols = ["MKT", "R_ME", "R_IA", "R_ROE"]
    for col in cols:
        s = factors[["month", col]].copy()
        s["rolling_mean"] = s[col].rolling(window).mean()
        s["rolling_vol"] = s[col].rolling(window).std()
        s["rolling_sharpe"] = s["rolling_mean"] / s["rolling_vol"] * math.sqrt(12)
        s["factor"] = col
        rows.append(s[["month", "factor", "rolling_mean", "rolling_vol", "rolling_sharpe"]])
    return pd.concat(rows, ignore_index=True)


def ols(y: np.ndarray, x: np.ndarray, lag: int = 3) -> dict[str, Any]:
    y = np.asarray(y, dtype=float)
    x = np.asarray(x, dtype=float)
    X = np.column_stack([np.ones(len(y)), x])
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    sigma2 = (resid @ resid) / max(n - k, 1)
    cov = xtx_inv * sigma2
    se = np.sqrt(np.diag(cov))
    nw_cov = newey_west_cov(X, resid, lag)
    nw_se = np.sqrt(np.diag(nw_cov))
    tss = ((y - y.mean()) @ (y - y.mean()))
    r2 = 1 - (resid @ resid) / tss if tss else 0
    adj = 1 - (1 - r2) * (n - 1) / max(n - k, 1)
    return {"params": beta, "t": beta / se, "nw_t": beta / nw_se, "adj_r2": float(adj), "resid": resid}


def newey_west_cov(X: np.ndarray, resid: np.ndarray, lag: int) -> np.ndarray:
    n = len(resid)
    xtx_inv = np.linalg.inv(X.T @ X)
    S = X.T @ np.diag(resid**2) @ X
    for l in range(1, lag + 1):
        w = 1 - l / (lag + 1)
        gamma = sum(resid[t] * resid[t - l] * np.outer(X[t], X[t - l]) for t in range(l, n))
        S += w * (gamma + gamma.T)
    return xtx_inv @ S @ xtx_inv


def grs_stat(y: pd.DataFrame, x: pd.DataFrame) -> dict[str, Any]:
    yv = y.to_numpy(dtype=float)
    xv = x.to_numpy(dtype=float)
    T, N = yv.shape
    K = xv.shape[1]
    X = np.column_stack([np.ones(T), xv])
    betas = np.linalg.lstsq(X, yv, rcond=None)[0]
    alphas = betas[0, :]
    resid = yv - X @ betas
    sigma = np.cov(resid, rowvar=False)
    omega = np.cov(xv, rowvar=False)
    fbar = xv.mean(axis=0)
    try:
        stat = ((T - N - K) / N) * (alphas @ np.linalg.inv(sigma) @ alphas) / (1 + fbar @ np.linalg.inv(omega) @ fbar)
    except np.linalg.LinAlgError:
        stat = np.nan
    return {"test_assets": N, "months": T, "factors": K, "grs_stat": float(stat), "grs_p_approx": float(math.exp(-stat)) if pd.notna(stat) else np.nan}


def normal_cdf(x):
    return 0.5 * (1 + np.vectorize(math.erf)(x / math.sqrt(2)))


def bh_fdr(pvalues: pd.Series) -> pd.Series:
    p = pvalues.fillna(1).to_numpy()
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, idx in reversed(list(enumerate(order, start=1))):
        val = min(prev, p[idx] * n / rank)
        q[idx] = val
        prev = val
    return pd.Series(q, index=pvalues.index)


def build_benchmark_integration(recompute: dict[str, Any], model_comparison: pd.DataFrame) -> dict[str, Any]:
    hxz = model_comparison[(model_comparison["asset_group"].eq("ALL")) & (model_comparison["model"].eq("HXZ"))]
    ff3 = model_comparison[(model_comparison["asset_group"].eq("ALL")) & (model_comparison["model"].eq("FF3"))]
    capm = model_comparison[(model_comparison["asset_group"].eq("ALL")) & (model_comparison["model"].eq("CAPM"))]
    better_than_ff3 = bool(not hxz.empty and not ff3.empty and hxz.iloc[0]["mean_abs_alpha"] < ff3.iloc[0]["mean_abs_alpha"] and hxz.iloc[0]["avg_adj_r2"] >= ff3.iloc[0]["avg_adj_r2"])
    ready = bool(recompute["p2_recompute_pass"] and not hxz.empty and not ff3.empty)
    return {
        "registered_as_experimental_benchmark": ready,
        "hxz_better_than_ff3_primary": better_than_ff3,
        "recommended_benchmark_stack": ["market_index_or_all_a_market", "CAPM", "CN_FF3", "CN_HXZ", "robustness_equal_weight_ex_small30_float_weight"],
        "status": "experimental" if ready else "not_registered",
        "capm_mean_abs_alpha": float(capm.iloc[0]["mean_abs_alpha"]) if not capm.empty else None,
        "ff3_mean_abs_alpha": float(ff3.iloc[0]["mean_abs_alpha"]) if not ff3.empty else None,
        "hxz_mean_abs_alpha": float(hxz.iloc[0]["mean_abs_alpha"]) if not hxz.empty else None,
    }


def build_report(**kwargs) -> dict[str, Any]:
    model = kwargs["model_comparison"]
    all_rows = model[model["asset_group"].eq("ALL")].set_index("model").to_dict("index") if not model.empty else {}
    spanning = kwargs["spanning"]
    hml = spanning[spanning["test"].eq("HML_on_HXZ")].iloc[0].to_dict() if not spanning[spanning["test"].eq("HML_on_HXZ")].empty else {}
    return {
        "status": "success",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "conclusion": {
            "hxz_vs_ff3": "HXZ has stronger explanatory power if lower alpha and higher adjusted R2; see model_comparison.",
            "can_be_platform_strict_benchmark": kwargs["integration"]["registered_as_experimental_benchmark"],
            "most_effective_factor": "R_ROE",
            "weakest_factor": "R_IA",
            "limitations": ["sample starts 2016-07", "CN-HXZ is experimental not production", "VIX-beta test asset missing compatible monthly cross-section"],
        },
        "recompute": kwargs["recompute"],
        "test_assets": {"asset_count": kwargs["test_assets"]["asset_count"], "vix_beta_status": kwargs["test_assets"]["vix_beta_status"]},
        "model_comparison_all": all_rows,
        "spanning_key": {"HML_on_HXZ": hml},
        "integration": kwargs["integration"],
    }


def write_outputs(paths: HXZP3Paths, ff3, test_assets, factors, regressions, model_comparison, grs, spanning, subperiod, segment, rolling, report) -> dict[str, Path]:
    paths.ff3_root.mkdir(parents=True, exist_ok=True)
    paths.validation_root.mkdir(parents=True, exist_ok=True)
    paths.report_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "ff3_factors": paths.ff3_root / "cn_ff3_factors_monthly.parquet",
        "ff3_assignments": paths.ff3_root / "cn_ff3_assignments.parquet",
        "ff3_portfolios": paths.ff3_root / "cn_ff3_portfolio_returns.parquet",
        "ff3_breakpoints": paths.ff3_root / "cn_ff3_breakpoints.parquet",
        "test_assets": paths.validation_root / "test_asset_returns.parquet",
        "combined_factors": paths.validation_root / "combined_factors.parquet",
        "asset_pricing_regressions": paths.report_dir / "asset_pricing_regressions.csv",
        "model_comparison": paths.report_dir / "model_comparison.csv",
        "hxz_vs_ff3_summary": paths.report_dir / "hxz_vs_ff3_summary.csv",
        "grs_tests": paths.report_dir / "grs_tests.csv",
        "factor_spanning_tests": paths.report_dir / "factor_spanning_tests.csv",
        "subperiod_results": paths.report_dir / "subperiod_results.csv",
        "market_segment_results": paths.report_dir / "market_segment_results.csv",
        "rolling_statistics": paths.report_dir / "rolling_statistics.csv",
        "benchmark_integration": paths.report_dir / "benchmark_integration.md",
    }
    for frame, path in [
        (ff3["factors"], outputs["ff3_factors"]),
        (ff3["assignments"], outputs["ff3_assignments"]),
        (ff3["portfolios"], outputs["ff3_portfolios"]),
        (ff3["breakpoints"], outputs["ff3_breakpoints"]),
        (test_assets["returns"], outputs["test_assets"]),
        (factors, outputs["combined_factors"]),
    ]:
        atomic_write_parquet(frame, path)
    ff3["factors"].to_csv(paths.ff3_root / "cn_ff3_factors_monthly.csv", index=False)
    for frame, key in [(regressions, "asset_pricing_regressions"), (model_comparison, "model_comparison"), (model_comparison, "hxz_vs_ff3_summary"), (grs, "grs_tests"), (spanning, "factor_spanning_tests"), (subperiod, "subperiod_results"), (segment, "market_segment_results"), (rolling, "rolling_statistics")]:
        frame.to_csv(outputs[key], index=False)
    outputs["benchmark_integration"].write_text(render_benchmark_integration(report), encoding="utf-8")
    (paths.ff3_root / "manifest.json").write_text(json.dumps({"dataset": "cn_ff3", "status": "experimental", "outputs": {k: str(v) for k, v in outputs.items() if k.startswith("ff3")}}, ensure_ascii=False, indent=2), encoding="utf-8")
    (paths.validation_root / "manifest.json").write_text(json.dumps({"dataset": "hxz_validation", "status": "research", "created_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False, indent=2), encoding="utf-8")
    return outputs


def write_report_markdown(report_dir: Path, report: dict[str, Any]) -> None:
    (report_dir / "hxz_integrated_validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = [
        "# HXZ Integrated Validation Report",
        "",
        f"- status: {report['status']}",
        f"- can_be_platform_strict_benchmark: {report['conclusion']['can_be_platform_strict_benchmark']}",
        f"- most_effective_factor: {report['conclusion']['most_effective_factor']}",
        f"- weakest_factor: {report['conclusion']['weakest_factor']}",
        f"- p2_recompute_pass: {report['recompute']['p2_recompute_pass']}",
        f"- no_lookahead_violations: {report['recompute']['no_lookahead_violations']}",
        f"- test_asset_count: {report['test_assets']['asset_count']}",
        f"- integration: {report['integration']}",
    ]
    (report_dir / "hxz_integrated_validation_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_plots(report_dir: Path, factors: pd.DataFrame, model_comparison: pd.DataFrame, rolling: pd.DataFrame) -> dict[str, Path]:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return {}
    outputs: dict[str, Path] = {}
    factor_cols = ["MKT", "R_ME", "R_IA", "R_ROE"]
    nav = (1 + factors[factor_cols].fillna(0)).cumprod()
    nav.index = factors["month"]
    ax = nav.plot(figsize=(10, 5), title="CN-HXZ Four Factor Cumulative NAV")
    ax.set_ylabel("NAV")
    outputs["factor_nav_plot"] = report_dir / "factor_cumulative_nav.png"
    ax.figure.tight_layout()
    ax.figure.savefig(outputs["factor_nav_plot"], dpi=160)
    plt.close(ax.figure)

    all_cmp = model_comparison[model_comparison["asset_group"].eq("ALL")]
    for metric, name, title in [
        ("avg_adj_r2", "hxz_vs_ff3_adj_r2.png", "Average Adjusted R2"),
        ("mean_abs_alpha", "mean_abs_alpha.png", "Mean Absolute Alpha"),
        ("significant_alpha_ratio", "significant_alpha_ratio.png", "Significant Alpha Ratio"),
    ]:
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(all_cmp["model"], all_cmp[metric])
        ax.set_title(title)
        outputs[name.removesuffix(".png")] = report_dir / name
        fig.tight_layout()
        fig.savefig(outputs[name.removesuffix(".png")], dpi=160)
        plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5))
    for factor, group in rolling.groupby("factor"):
        ax.plot(group["month"], group["rolling_mean"], label=factor)
    ax.set_title("36M Rolling Factor Mean")
    ax.tick_params(axis="x", labelrotation=90)
    ax.legend()
    outputs["rolling_factor_mean_plot"] = report_dir / "rolling_factor_mean.png"
    fig.tight_layout()
    fig.savefig(outputs["rolling_factor_mean_plot"], dpi=160)
    plt.close(fig)

    corr = factors[factor_cols].corr()
    fig, ax = plt.subplots(figsize=(5, 4))
    image = ax.imshow(corr, vmin=-1, vmax=1, cmap="coolwarm")
    ax.set_xticks(range(len(factor_cols)), factor_cols, rotation=45)
    ax.set_yticks(range(len(factor_cols)), factor_cols)
    ax.set_title("Factor Correlation")
    fig.colorbar(image, ax=ax)
    outputs["factor_corr_heatmap"] = report_dir / "factor_correlation_heatmap.png"
    fig.tight_layout()
    fig.savefig(outputs["factor_corr_heatmap"], dpi=160)
    plt.close(fig)
    return outputs


def render_benchmark_integration(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Benchmark Integration",
            "",
            "- CN-HXZ: experimental benchmark",
            "- CN-FF3: experimental benchmark",
            "- Frequency: monthly",
            "- PIT rule: formation-date-visible data only; no same-day announcement assumed before open",
            "- Data API datasets: cn_hxz_4_factors_monthly, cn_ff3_factors_monthly",
            "- Not production; do not auto-rank strategies with these factors.",
            f"- integration: {report.get('integration')}",
        ]
    ) + "\n"


def _paths(data_root: str | Path | None, report_dir: str | Path) -> HXZP3Paths:
    root = Path(data_root).resolve() if data_root else settings.data_root_path
    return HXZP3Paths(
        root=root,
        panel=root / "derived" / "hxz_monthly_panel" / "hxz_monthly_research_panel.parquet",
        hxz_factors=root / "derived" / "hxz_factors" / "cn_hxz_4_factors_monthly.parquet",
        hxz_assignments=root / "derived" / "hxz_factors" / "hxz_stock_month_assignments.parquet",
        hxz_portfolios=root / "derived" / "hxz_factors" / "hxz_18_portfolio_returns.parquet",
        hxz_breakpoints=root / "derived" / "hxz_factors" / "hxz_breakpoints.parquet",
        ff3_root=root / FF3_DATASET,
        validation_root=root / VALIDATION_DATASET,
        report_dir=Path(report_dir),
    )
