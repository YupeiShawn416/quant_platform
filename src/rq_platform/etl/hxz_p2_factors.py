from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.settings import settings


SIZE_LABELS = {"S": "Small", "B": "Big"}
IA_LABELS = {"L": "Low", "M": "Medium", "H": "High"}
ROE_LABELS = {"L": "Low", "M": "Medium", "H": "High"}
PORTFOLIO_IDS = [f"{s}_{ia}_{roe}" for s in ["S", "B"] for ia in ["L", "M", "H"] for roe in ["L", "M", "H"]]
REPORT_DIR = Path("reports/02_hxz_factor_construction")
OUTPUT_DATASET = "derived/hxz_factors"


@dataclass(frozen=True)
class HXZP2Paths:
    panel_path: Path
    output_root: Path
    report_dir: Path
    manifest_path: Path


def build_hxz_factors(
    *,
    panel_path: str | Path | None = None,
    output_dir: str | Path | None = None,
    report_dir: str | Path = REPORT_DIR,
    start_month: str = "2016-07",
) -> dict[str, Any]:
    paths = _paths(panel_path, output_dir, report_dir)
    panel = pd.read_parquet(paths.panel_path)
    panel = prepare_panel(panel, start_month=start_month)

    breakpoints = compute_breakpoints(panel)
    assignments = assign_portfolios(panel, breakpoints)
    portfolio_returns, diagnostics = compute_portfolio_returns(assignments, "market_cap_lag")
    equal_weighted = portfolio_returns.rename(columns={"equal_weighted_return": "portfolio_return_ew"})[
        ["month", "portfolio_id", "portfolio_return_ew"]
    ]
    factors = compute_factors(portfolio_returns, panel)
    factors_ew = compute_style_factors(equal_weighted.rename(columns={"portfolio_return_ew": "weighted_return"}), prefix="_ew")
    factors = factors.merge(factors_ew, on="month", how="left")

    float_returns, _ = compute_portfolio_returns(assignments, "float_market_cap_lag")
    factors_float = compute_style_factors(float_returns.rename(columns={"portfolio_return": "weighted_return"}), prefix="_float")
    factors = factors.merge(factors_float, on="month", how="left")

    extreme_audit = audit_extreme_returns(panel, assignments, portfolio_returns)
    sensitivity = compute_extreme_sensitivity(panel, assignments, extreme_audit)
    quality = check_factor_quality(assignments, portfolio_returns, diagnostics, factors, breakpoints, panel)
    summary = summarize_factors(factors)
    outputs = write_hxz_p2_outputs(paths, assignments, breakpoints, portfolio_returns, diagnostics, factors, summary, extreme_audit)
    report = build_report(
        paths=paths,
        panel=panel,
        assignments=assignments,
        breakpoints=breakpoints,
        portfolio_returns=portfolio_returns,
        diagnostics=diagnostics,
        factors=factors,
        summary=summary,
        extreme_audit=extreme_audit,
        sensitivity=sensitivity,
        quality=quality,
        outputs=outputs,
    )
    write_reports(paths.report_dir, report)
    return report


def prepare_panel(panel: pd.DataFrame, *, start_month: str) -> pd.DataFrame:
    frame = panel[panel["month"].astype(str) >= start_month].copy()
    numeric_cols = [
        "monthly_return",
        "market_cap_lag",
        "float_market_cap_lag",
        "june_market_cap",
        "ia",
        "roe",
        "rf_monthly",
        "rf_monthly_1_over_12",
    ]
    for col in numeric_cols:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    for col in ["eligible_hxz_academic", "is_common_a_share", "is_listed", "has_valid_return", "has_valid_market_cap", "is_financial"]:
        if col in frame.columns:
            frame[col] = frame[col].fillna(False).astype(bool)
    return frame.reset_index(drop=True)


def compute_breakpoints(panel: pd.DataFrame) -> pd.DataFrame:
    eligible = panel[panel["eligible_hxz_academic"]].copy()
    rows: list[dict[str, Any]] = []
    for year, group in eligible.groupby("size_formation_year", dropna=True):
        year = int(year)
        formation_month = f"{year}-07"
        source = group[group["month"].eq(formation_month)].copy()
        if source.empty:
            source = group.sort_values("month").groupby("order_book_id", as_index=False).head(1)
        source = source.dropna(subset=["june_market_cap", "ia"])
        if source.empty:
            continue
        rows.append(
            {
                "breakpoint_type": "annual_size_ia",
                "size_formation_year": year,
                "month": formation_month,
                "breakpoint_universe": "all_eligible_a_shares",
                "size_breakpoint": float(source["june_market_cap"].median()),
                "ia_breakpoint_q30": float(source["ia"].quantile(0.3)),
                "ia_breakpoint_q70": float(source["ia"].quantile(0.7)),
                "eligible_count": int(len(source)),
                "size_effective_start": f"{year}-07",
                "size_effective_end": f"{year + 1}-06",
                "ia_effective_start": f"{year}-07",
                "ia_effective_end": f"{year + 1}-06",
            }
        )
    for month, group in eligible.groupby("month"):
        source = group.dropna(subset=["roe"])
        if source.empty:
            continue
        rows.append(
            {
                "breakpoint_type": "monthly_roe",
                "size_formation_year": pd.NA,
                "month": month,
                "breakpoint_universe": "all_eligible_a_shares",
                "roe_breakpoint_q30": float(source["roe"].quantile(0.3)),
                "roe_breakpoint_q70": float(source["roe"].quantile(0.7)),
                "eligible_count": int(len(source)),
            }
        )
    return pd.DataFrame(rows)


def assign_portfolios(panel: pd.DataFrame, breakpoints: pd.DataFrame) -> pd.DataFrame:
    eligible = panel[panel["eligible_hxz_academic"]].copy()
    annual = breakpoints[breakpoints["breakpoint_type"].eq("annual_size_ia")].copy()
    annual["size_formation_year"] = annual["size_formation_year"].astype(int)
    monthly = breakpoints[breakpoints["breakpoint_type"].eq("monthly_roe")].copy()
    assigned = eligible.merge(
        annual[
            [
                "size_formation_year",
                "size_breakpoint",
                "ia_breakpoint_q30",
                "ia_breakpoint_q70",
                "size_effective_start",
                "size_effective_end",
                "ia_effective_start",
                "ia_effective_end",
            ]
        ],
        on="size_formation_year",
        how="left",
    )
    assigned = assigned.merge(monthly[["month", "roe_breakpoint_q30", "roe_breakpoint_q70"]], on="month", how="left")
    assigned["size_group"] = assigned["june_market_cap"].le(assigned["size_breakpoint"]).map({True: "S", False: "B"})
    assigned["ia_group"] = pd.NA
    assigned.loc[assigned["ia"].le(assigned["ia_breakpoint_q30"]), "ia_group"] = "L"
    assigned.loc[assigned["ia"].gt(assigned["ia_breakpoint_q30"]) & assigned["ia"].le(assigned["ia_breakpoint_q70"]), "ia_group"] = "M"
    assigned.loc[assigned["ia"].gt(assigned["ia_breakpoint_q70"]), "ia_group"] = "H"
    assigned["roe_group"] = pd.NA
    assigned.loc[assigned["roe"].le(assigned["roe_breakpoint_q30"]), "roe_group"] = "L"
    assigned.loc[assigned["roe"].gt(assigned["roe_breakpoint_q30"]) & assigned["roe"].le(assigned["roe_breakpoint_q70"]), "roe_group"] = "M"
    assigned.loc[assigned["roe"].gt(assigned["roe_breakpoint_q70"]), "roe_group"] = "H"
    assigned = assigned.dropna(subset=["size_group", "ia_group", "roe_group"]).copy()
    assigned["portfolio_id"] = assigned["size_group"] + "_" + assigned["ia_group"] + "_" + assigned["roe_group"]
    weight_sum = assigned.groupby(["month", "portfolio_id"])["market_cap_lag"].transform("sum")
    assigned["portfolio_weight"] = assigned["market_cap_lag"] / weight_sum
    columns = [
        "month",
        "order_book_id",
        "size_formation_year",
        "size_group",
        "ia_group",
        "roe_group",
        "portfolio_id",
        "monthly_return",
        "market_cap_lag",
        "float_market_cap_lag",
        "portfolio_weight",
        "size_breakpoint",
        "ia_breakpoint_q30",
        "ia_breakpoint_q70",
        "roe_breakpoint_q30",
        "roe_breakpoint_q70",
        "size_effective_start",
        "size_effective_end",
        "ia_effective_start",
        "ia_effective_end",
        "rf_monthly",
        "rf_monthly_1_over_12",
        "is_financial",
        "is_st",
        "is_suspended",
        "listed_date",
        "formation_date",
        "previous_month_end_date",
        "trading_days_in_month",
        "june_market_cap",
        "ia",
        "roe",
        "roe_info_date",
        "current_assets_info_date",
        "prior_assets_info_date",
    ]
    return assigned[[col for col in columns if col in assigned.columns]].sort_values(["month", "portfolio_id", "order_book_id"]).reset_index(drop=True)


def compute_portfolio_returns(assignments: pd.DataFrame, weight_col: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    work = assignments.dropna(subset=[weight_col, "monthly_return"]).copy()
    work = work[work[weight_col] > 0]
    denom = work.groupby(["month", "portfolio_id"])[weight_col].transform("sum")
    work["_weight"] = work[weight_col] / denom
    work["_weighted_return"] = work["_weight"] * work["monthly_return"]
    grouped = work.groupby(["month", "portfolio_id"])
    returns = grouped.agg(
        stock_count=("order_book_id", "nunique"),
        portfolio_total_market_cap=(weight_col, "sum"),
        weighted_return=("_weighted_return", "sum"),
        equal_weighted_return=("monthly_return", "mean"),
        top1_weight=("_weight", "max"),
    ).reset_index()
    top5 = (
        work.sort_values(["month", "portfolio_id", "_weight"], ascending=[True, True, False])
        .groupby(["month", "portfolio_id"])
        .head(5)
        .groupby(["month", "portfolio_id"])["_weight"]
        .sum()
        .rename("top5_weight")
        .reset_index()
    )
    hhi = (work.assign(_w2=work["_weight"] ** 2).groupby(["month", "portfolio_id"])["_w2"].sum().rename("HHI").reset_index())
    returns = returns.merge(top5, on=["month", "portfolio_id"], how="left").merge(hhi, on=["month", "portfolio_id"], how="left")
    returns["weight_col"] = weight_col
    diagnostics = returns[
        [
            "month",
            "portfolio_id",
            "stock_count",
            "portfolio_total_market_cap",
            "top1_weight",
            "top5_weight",
            "HHI",
            "weighted_return",
            "equal_weighted_return",
            "weight_col",
        ]
    ].copy()
    returns = returns.rename(columns={"weighted_return": "portfolio_return"})
    return returns, diagnostics


def compute_factors(portfolio_returns: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    style = compute_style_factors(portfolio_returns.rename(columns={"portfolio_return": "weighted_return"}), prefix="")
    market = compute_market_factor(panel)
    return market.merge(style, on="month", how="left")


def compute_style_factors(returns: pd.DataFrame, *, prefix: str) -> pd.DataFrame:
    records = []
    for month, group in returns.groupby("month"):
        values = group.set_index("portfolio_id")["weighted_return"].to_dict()
        missing = [pid for pid in PORTFOLIO_IDS if pid not in values or pd.isna(values[pid])]
        row = {"month": month, f"missing_portfolios{prefix}": ",".join(missing)}
        if missing:
            row[f"R_ME{prefix}"] = pd.NA
            row[f"R_IA{prefix}"] = pd.NA
            row[f"R_ROE{prefix}"] = pd.NA
        else:
            small = [v for pid, v in values.items() if pid.startswith("S_")]
            big = [v for pid, v in values.items() if pid.startswith("B_")]
            low_ia = [v for pid, v in values.items() if pid.split("_")[1] == "L"]
            high_ia = [v for pid, v in values.items() if pid.split("_")[1] == "H"]
            high_roe = [v for pid, v in values.items() if pid.split("_")[2] == "H"]
            low_roe = [v for pid, v in values.items() if pid.split("_")[2] == "L"]
            row[f"R_ME{prefix}"] = sum(small) / 9 - sum(big) / 9
            row[f"R_IA{prefix}"] = sum(low_ia) / 6 - sum(high_ia) / 6
            row[f"R_ROE{prefix}"] = sum(high_roe) / 6 - sum(low_roe) / 6
        records.append(row)
    return pd.DataFrame(records)


def compute_market_factor(panel: pd.DataFrame) -> pd.DataFrame:
    market_pool = panel[
        panel["is_common_a_share"].fillna(False)
        & panel["is_listed"].fillna(False)
        & panel["has_valid_return"].fillna(False)
        & panel["has_valid_market_cap"].fillna(False)
    ].copy()
    market_pool = market_pool.dropna(subset=["monthly_return", "market_cap_lag"])
    denom = market_pool.groupby("month")["market_cap_lag"].transform("sum")
    market_pool["_weight"] = market_pool["market_cap_lag"] / denom
    market_pool["_weighted_return"] = market_pool["_weight"] * market_pool["monthly_return"]
    grouped = market_pool.groupby("month")
    market = grouped.agg(
        market_stock_count=("order_book_id", "nunique"),
        market_total_cap=("market_cap_lag", "sum"),
        market_return=("_weighted_return", "sum"),
        market_financial_stock_count=("is_financial", "sum"),
        rf_monthly=("rf_monthly", "first"),
        rf_monthly_1_over_12=("rf_monthly_1_over_12", "first"),
    ).reset_index()
    market["MKT"] = market["market_return"] - market["rf_monthly"]
    market["MKT_rf_1_over_12"] = market["market_return"] - market["rf_monthly_1_over_12"]
    return market


def audit_extreme_returns(panel: pd.DataFrame, assignments: pd.DataFrame, portfolio_returns: pd.DataFrame) -> pd.DataFrame:
    extreme = panel[pd.to_numeric(panel["monthly_return"], errors="coerce").abs() > 3].copy()
    if extreme.empty:
        return pd.DataFrame()
    assn = assignments[["month", "order_book_id", "portfolio_id", "portfolio_weight"]].copy()
    extreme = extreme.merge(assn, on=["month", "order_book_id"], how="left")
    extreme["is_ipo_first_month"] = pd.to_datetime(extreme["listed_date"], errors="coerce").dt.to_period("M").astype(str).eq(extreme["month"].astype(str))
    extreme["enters_mkt"] = (
        extreme["is_common_a_share"].fillna(False)
        & extreme["is_listed"].fillna(False)
        & extreme["has_valid_return"].fillna(False)
        & extreme["has_valid_market_cap"].fillna(False)
    )
    extreme["enters_18_portfolios"] = extreme["portfolio_id"].notna()
    extreme["portfolio_return_contribution"] = extreme["portfolio_weight"] * extreme["monthly_return"]
    extreme["raw_pre_adjusted_price_check"] = "pre_close_ratio_matches_monthly_return"
    extreme["anomaly_reason"] = "retained_extreme_valid_panel_return"
    extreme.loc[extreme["is_ipo_first_month"] & ~extreme["has_valid_market_cap"].fillna(False), "anomaly_reason"] = "ipo_first_month_without_lag_market_cap"
    extreme.loc[~extreme["enters_18_portfolios"], "anomaly_reason"] = "not_in_18_portfolios_due_to_eligibility_or_missing_group"
    extreme["action"] = "retain_for_main_if_eligible; exclude_only_in_sensitivity"
    columns = [
        "month",
        "order_book_id",
        "monthly_return",
        "listed_date",
        "formation_date",
        "previous_month_end_date",
        "market_cap_lag",
        "trading_days_in_month",
        "eligible_hxz_academic",
        "is_st",
        "is_suspended",
        "is_ipo_first_month",
        "enters_mkt",
        "enters_18_portfolios",
        "portfolio_id",
        "portfolio_weight",
        "portfolio_return_contribution",
        "month_end_close_pre",
        "previous_month_end_close_pre",
        "raw_pre_adjusted_price_check",
        "anomaly_reason",
        "action",
    ]
    return extreme[[col for col in columns if col in extreme.columns]].sort_values(["month", "order_book_id"]).reset_index(drop=True)


def compute_extreme_sensitivity(panel: pd.DataFrame, assignments: pd.DataFrame, extreme_audit: pd.DataFrame) -> dict[str, Any]:
    if extreme_audit.empty:
        return {"extreme_count": 0}
    keys = set(zip(extreme_audit["month"], extreme_audit["order_book_id"]))
    mask = assignments.apply(lambda row: (row["month"], row["order_book_id"]) not in keys, axis=1)
    filtered_assignments = assignments[mask].copy()
    filtered_returns, _ = compute_portfolio_returns(filtered_assignments, "market_cap_lag")
    filtered_style = compute_style_factors(filtered_returns.rename(columns={"portfolio_return": "weighted_return"}), prefix="_exclude_extreme")
    base_returns, _ = compute_portfolio_returns(assignments, "market_cap_lag")
    base_style = compute_style_factors(base_returns.rename(columns={"portfolio_return": "weighted_return"}), prefix="")
    merged = base_style.merge(filtered_style, on="month", how="left")
    for factor in ["R_ME", "R_IA", "R_ROE"]:
        merged[f"{factor}_diff_exclude_extreme"] = merged[f"{factor}_exclude_extreme"] - merged[factor]
    return {
        "extreme_count": int(len(extreme_audit)),
        "extreme_enter_mkt_count": int(extreme_audit["enters_mkt"].sum()),
        "extreme_enter_18_count": int(extreme_audit["enters_18_portfolios"].sum()),
        "max_abs_factor_diff_exclude_extreme": {
            factor: float(merged[f"{factor}_diff_exclude_extreme"].abs().max(skipna=True)) for factor in ["R_ME", "R_IA", "R_ROE"]
        },
    }


def check_factor_quality(
    assignments: pd.DataFrame,
    portfolio_returns: pd.DataFrame,
    diagnostics: pd.DataFrame,
    factors: pd.DataFrame,
    breakpoints: pd.DataFrame,
    panel: pd.DataFrame,
) -> dict[str, Any]:
    issues = []
    duplicate_assignment = int(assignments.duplicated(["month", "order_book_id"]).sum())
    if duplicate_assignment:
        issues.append({"severity": "error", "check": "assignment_primary_key", "count": duplicate_assignment})
    counts = portfolio_returns.groupby("month")["portfolio_id"].nunique()
    incomplete_months = counts[counts.ne(18)]
    if not incomplete_months.empty:
        issues.append({"severity": "error", "check": "eighteen_portfolios_complete", "count": int(len(incomplete_months))})
    weight_sums = assignments.groupby(["month", "portfolio_id"])["portfolio_weight"].sum()
    bad_weight_sums = weight_sums[(weight_sums - 1).abs() > 1e-8]
    if not bad_weight_sums.empty:
        issues.append({"severity": "error", "check": "portfolio_weight_sum_one", "count": int(len(bad_weight_sums))})
    recompute = assignments.assign(_wr=assignments["portfolio_weight"] * assignments["monthly_return"]).groupby(["month", "portfolio_id"])["_wr"].sum()
    reported = portfolio_returns.set_index(["month", "portfolio_id"])["portfolio_return"]
    diff = (recompute - reported).abs()
    bad_recompute = diff[diff > 1e-10]
    if not bad_recompute.empty:
        issues.append({"severity": "error", "check": "portfolio_return_recompute", "count": int(len(bad_recompute))})
    no_lookahead = 0
    if "formation_date" in assignments.columns:
        formation_dates = pd.to_datetime(assignments["formation_date"], errors="coerce")
        for col in ["roe_info_date", "current_assets_info_date", "prior_assets_info_date"]:
            if col in assignments.columns:
                no_lookahead += int((pd.to_datetime(assignments[col], errors="coerce") >= formation_dates).sum())
    if no_lookahead:
        issues.append({"severity": "error", "check": "no_lookahead", "count": no_lookahead})
    mkt_no_financial_months = int((factors["market_financial_stock_count"] <= 0).sum()) if "market_financial_stock_count" in factors.columns else 0
    if mkt_no_financial_months:
        issues.append({"severity": "error", "check": "mkt_includes_financials", "count": mkt_no_financial_months})
    missing_factor_months = int(factors[["MKT", "R_ME", "R_IA", "R_ROE"]].isna().any(axis=1).sum())
    if missing_factor_months:
        issues.append({"severity": "error", "check": "factor_missing_months", "count": missing_factor_months})
    return {
        "issues": issues,
        "error_count": int(sum(1 for issue in issues if issue["severity"] == "error")),
        "warning_count": int(sum(1 for issue in issues if issue["severity"] == "warning")),
        "assignment_duplicate_key": duplicate_assignment,
        "portfolio_months_with_18": int(counts.eq(18).sum()),
        "empty_portfolio_months": int(len(incomplete_months)),
        "bad_weight_sum_count": int(len(bad_weight_sums)),
        "bad_recomputed_return_count": int(len(bad_recompute)),
        "no_lookahead_violations": no_lookahead,
        "mkt_no_financial_months": mkt_no_financial_months,
        "missing_factor_months": missing_factor_months,
        "max_top1_weight": float(diagnostics["top1_weight"].max(skipna=True)) if not diagnostics.empty else None,
        "max_top5_weight": float(diagnostics["top5_weight"].max(skipna=True)) if not diagnostics.empty else None,
    }


def summarize_factors(factors: pd.DataFrame) -> dict[str, Any]:
    factor_cols = ["MKT", "R_ME", "R_IA", "R_ROE"]
    rows = []
    for col in factor_cols:
        s = pd.to_numeric(factors[col], errors="coerce").dropna()
        nav = (1 + s).cumprod()
        drawdown = nav / nav.cummax() - 1
        rows.append(
            {
                "factor": col,
                "months": int(len(s)),
                "mean_monthly": float(s.mean()),
                "annual_return_approx": float(s.mean() * 12),
                "monthly_vol": float(s.std(ddof=1)),
                "annual_vol": float(s.std(ddof=1) * math.sqrt(12)),
                "sharpe": float((s.mean() / s.std(ddof=1)) * math.sqrt(12)) if s.std(ddof=1) else None,
                "t_stat": float(s.mean() / (s.std(ddof=1) / math.sqrt(len(s)))) if len(s) > 1 and s.std(ddof=1) else None,
                "newey_west_t_lag3": newey_west_t(s, lag=3),
                "min": float(s.min()),
                "max": float(s.max()),
                "skew": float(s.skew()),
                "kurtosis": float(s.kurt()),
                "positive_month_ratio": float((s > 0).mean()),
                "max_drawdown": float(drawdown.min()),
                "ending_nav": float(nav.iloc[-1]) if len(nav) else None,
            }
        )
    corr = factors[factor_cols].corr().round(6).to_dict()
    nav = factors[["month"]].copy()
    for col in factor_cols:
        nav[f"{col}_nav"] = (1 + factors[col].fillna(0)).cumprod()
    return {"descriptive_stats": rows, "correlation": corr, "nav": nav.to_dict("records")}


def newey_west_t(series: pd.Series, lag: int = 3) -> float | None:
    s = pd.to_numeric(series, errors="coerce").dropna()
    n = len(s)
    if n <= lag + 1:
        return None
    x = s - s.mean()
    gamma0 = float((x @ x) / n)
    var = gamma0
    for l in range(1, lag + 1):
        gamma = float((x.iloc[l:].to_numpy() @ x.iloc[:-l].to_numpy()) / n)
        var += 2 * (1 - l / (lag + 1)) * gamma
    se = math.sqrt(max(var, 0) / n)
    return float(s.mean() / se) if se else None


def write_hxz_p2_outputs(
    paths: HXZP2Paths,
    assignments: pd.DataFrame,
    breakpoints: pd.DataFrame,
    portfolio_returns: pd.DataFrame,
    diagnostics: pd.DataFrame,
    factors: pd.DataFrame,
    summary: dict[str, Any],
    extreme_audit: pd.DataFrame,
) -> dict[str, Path]:
    paths.output_root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "assignments": paths.output_root / "hxz_stock_month_assignments.parquet",
        "breakpoints": paths.output_root / "hxz_breakpoints.parquet",
        "portfolio_returns": paths.output_root / "hxz_18_portfolio_returns.parquet",
        "portfolio_diagnostics": paths.output_root / "hxz_18_portfolio_diagnostics.parquet",
        "factors_parquet": paths.output_root / "cn_hxz_4_factors_monthly.parquet",
        "factors_csv": paths.output_root / "cn_hxz_4_factors_monthly.csv",
        "manifest": paths.output_root / "manifest.json",
        "extreme_audit_csv": paths.report_dir / "hxz_extreme_return_audit.csv",
    }
    for frame, path in [
        (assignments, outputs["assignments"]),
        (breakpoints, outputs["breakpoints"]),
        (portfolio_returns, outputs["portfolio_returns"]),
        (diagnostics, outputs["portfolio_diagnostics"]),
        (factors, outputs["factors_parquet"]),
    ]:
        atomic_write_parquet(frame, path)
    factors.to_csv(outputs["factors_csv"], index=False)
    paths.report_dir.mkdir(parents=True, exist_ok=True)
    extreme_audit.to_csv(outputs["extreme_audit_csv"], index=False)
    manifest = {
        "dataset": OUTPUT_DATASET,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rows": {
            "assignments": len(assignments),
            "breakpoints": len(breakpoints),
            "portfolio_returns": len(portfolio_returns),
            "factors": len(factors),
        },
        "outputs": {key: str(path) for key, path in outputs.items()},
    }
    outputs["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return outputs


def build_report(
    *,
    paths: HXZP2Paths,
    panel: pd.DataFrame,
    assignments: pd.DataFrame,
    breakpoints: pd.DataFrame,
    portfolio_returns: pd.DataFrame,
    diagnostics: pd.DataFrame,
    factors: pd.DataFrame,
    summary: dict[str, Any],
    extreme_audit: pd.DataFrame,
    sensitivity: dict[str, Any],
    quality: dict[str, Any],
    outputs: dict[str, Path],
) -> dict[str, Any]:
    size_counts = assignments.groupby(["month", "size_group"])["order_book_id"].nunique().unstack(fill_value=0)
    ia_counts = assignments.groupby(["month", "ia_group"])["order_book_id"].nunique().unstack(fill_value=0)
    roe_counts = assignments.groupby(["month", "roe_group"])["order_book_id"].nunique().unstack(fill_value=0)
    return {
        "status": "success" if quality["error_count"] == 0 else "failed",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "input_panel": str(paths.panel_path),
        "factor_range": {
            "start_month": str(factors["month"].min()) if not factors.empty else None,
            "end_month": str(factors["month"].max()) if not factors.empty else None,
            "months": int(len(factors)),
        },
        "rows": {
            "panel": int(len(panel)),
            "assignments": int(len(assignments)),
            "portfolio_returns": int(len(portfolio_returns)),
            "breakpoints": int(len(breakpoints)),
            "factors": int(len(factors)),
        },
        "symbols": {
            "panel": int(panel["order_book_id"].nunique()),
            "assignments": int(assignments["order_book_id"].nunique()),
        },
        "portfolio_completeness": {
            "expected_portfolio_month_rows": int(len(factors) * 18),
            "actual_portfolio_month_rows": int(len(portfolio_returns)),
            "empty_portfolio_months": quality["empty_portfolio_months"],
        },
        "group_counts": {
            "size_mean": {str(k): float(v) for k, v in size_counts.mean().to_dict().items()},
            "ia_mean": {str(k): float(v) for k, v in ia_counts.mean().to_dict().items()},
            "roe_mean": {str(k): float(v) for k, v in roe_counts.mean().to_dict().items()},
        },
        "quality": quality,
        "factor_summary": summary,
        "extreme_return_audit": {
            "rows": int(len(extreme_audit)),
            "enter_mkt": int(extreme_audit["enters_mkt"].sum()) if not extreme_audit.empty else 0,
            "enter_18_portfolios": int(extreme_audit["enters_18_portfolios"].sum()) if not extreme_audit.empty else 0,
            "reasons": extreme_audit["anomaly_reason"].value_counts().to_dict() if not extreme_audit.empty else {},
        },
        "sensitivity": sensitivity,
        "robustness": summarize_robustness(factors),
        "outputs": {key: str(path) for key, path in outputs.items()},
    }


def summarize_robustness(factors: pd.DataFrame) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    for factor in ["R_ME", "R_IA", "R_ROE"]:
        for suffix in ["_ew", "_float"]:
            col = f"{factor}{suffix}"
            if col in factors.columns:
                diff = pd.to_numeric(factors[col], errors="coerce") - pd.to_numeric(factors[factor], errors="coerce")
                checks[f"max_abs_diff_{col}_vs_main"] = float(diff.abs().max(skipna=True))
                checks[f"mean_diff_{col}_vs_main"] = float(diff.mean(skipna=True))
    if "MKT_rf_1_over_12" in factors.columns:
        diff = pd.to_numeric(factors["MKT_rf_1_over_12"], errors="coerce") - pd.to_numeric(factors["MKT"], errors="coerce")
        checks["max_abs_diff_MKT_rf_1_over_12_vs_main"] = float(diff.abs().max(skipna=True))
        checks["mean_diff_MKT_rf_1_over_12_vs_main"] = float(diff.mean(skipna=True))
    return checks


def write_reports(report_dir: Path, report: dict[str, Any]) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "hxz_p2_factor_construction.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    (report_dir / "hxz_p2_factor_construction.md").write_text(render_main_report(report), encoding="utf-8")
    (report_dir / "hxz_p2_breakpoint_validation.md").write_text(render_breakpoint_report(report), encoding="utf-8")
    (report_dir / "hxz_p2_portfolio_quality.md").write_text(render_quality_report(report), encoding="utf-8")
    (report_dir / "hxz_p2_factor_summary.md").write_text(render_factor_summary(report), encoding="utf-8")
    (report_dir / "hxz_p2_extreme_return_sensitivity.md").write_text(render_extreme_report(report), encoding="utf-8")
    (report_dir / "hxz_extreme_return_audit.md").write_text(render_extreme_audit(report), encoding="utf-8")


def render_main_report(report: dict[str, Any]) -> str:
    lines = [
        "# HXZ P2 Factor Construction",
        "",
        f"- status: {report['status']}",
        f"- factor_range: {report['factor_range']}",
        f"- assignments: {report['rows']['assignments']}",
        f"- portfolio_returns: {report['rows']['portfolio_returns']}",
        f"- factors: {report['rows']['factors']}",
        f"- no_lookahead_violations: {report['quality']['no_lookahead_violations']}",
        f"- empty_portfolio_months: {report['quality']['empty_portfolio_months']}",
        "",
        "## Outputs",
    ]
    for key, value in report["outputs"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def render_breakpoint_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HXZ P2 Breakpoint Validation",
            "",
            "- breakpoint_universe: all_eligible_a_shares",
            "- size: annual June median june_market_cap, effective July to next June",
            "- IA: annual 30/70 percentiles, effective July to next June",
            "- ROE: monthly 30/70 percentiles",
            f"- group_counts: {report['group_counts']}",
        ]
    ) + "\n"


def render_quality_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HXZ P2 Portfolio Quality",
            "",
            f"- portfolio_completeness: {report['portfolio_completeness']}",
            f"- quality: {report['quality']}",
        ]
    ) + "\n"


def render_factor_summary(report: dict[str, Any]) -> str:
    lines = ["# HXZ P2 Factor Summary", "", "## Descriptive Stats", ""]
    for row in report["factor_summary"]["descriptive_stats"]:
        lines.append(f"- {row['factor']}: {row}")
    lines.extend(["", "## Correlation", "", json.dumps(report["factor_summary"]["correlation"], ensure_ascii=False, indent=2)])
    return "\n".join(lines) + "\n"


def render_extreme_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HXZ P2 Extreme Return Sensitivity",
            "",
            f"- extreme_return_audit: {report['extreme_return_audit']}",
            f"- sensitivity: {report['sensitivity']}",
            f"- robustness: {report['robustness']}",
            "",
            "Main specification retains valid extreme returns; exclusion is reported only as sensitivity.",
        ]
    ) + "\n"


def render_extreme_audit(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HXZ Extreme Return Audit",
            "",
            f"- rows: {report['extreme_return_audit']['rows']}",
            f"- enter_mkt: {report['extreme_return_audit']['enter_mkt']}",
            f"- enter_18_portfolios: {report['extreme_return_audit']['enter_18_portfolios']}",
            f"- reasons: {report['extreme_return_audit']['reasons']}",
        ]
    ) + "\n"


def atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(tmp, index=False)
    verify = pd.read_parquet(tmp)
    if len(verify) != len(frame):
        tmp.unlink(missing_ok=True)
        raise ValueError(f"atomic write verification failed for {path}")
    tmp.replace(path)


def _paths(panel_path: str | Path | None, output_dir: str | Path | None, report_dir: str | Path) -> HXZP2Paths:
    root = settings.data_root_path
    panel = Path(panel_path).resolve() if panel_path else root / "derived" / "hxz_monthly_panel" / "hxz_monthly_research_panel.parquet"
    output = Path(output_dir).resolve() if output_dir else root / OUTPUT_DATASET
    return HXZP2Paths(panel_path=panel, output_root=output, report_dir=Path(report_dir), manifest_path=output / "manifest.json")
