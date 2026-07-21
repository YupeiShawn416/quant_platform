from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.settings import settings


PANEL_DATASET = "derived/hxz_monthly_panel"
REPORT_DIR = Path("reports/data_audit")
STATUS_COLUMNS = [
    "run_id",
    "created_at",
    "dataset",
    "start_month",
    "end_month",
    "status",
    "row_count",
    "output_files",
    "error",
]
FINANCIAL_SECTOR_NAMES = {"金融", "Financials"}
FINANCIAL_INDUSTRY_KEYWORDS = ("银行", "保险", "证券", "金融")
PIT_FIELDS = ["total_assets", "equity_parent_company", "total_equity", "net_profit_parent_company"]


@dataclass(frozen=True)
class HXZP1Paths:
    root: Path
    output_root: Path
    status_path: Path
    manifest_path: Path


def build_hxz_monthly_research_panel(
    *,
    data_root: str | Path | None = None,
    start_month: str | None = None,
    end_month: str | None = None,
    output_dir: str | Path | None = None,
    report_dir: str | Path = REPORT_DIR,
) -> dict[str, Any]:
    paths = _paths(data_root, output_dir)
    run_id = f"hxz_p1_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    started_at = datetime.now().isoformat(timespec="seconds")
    try:
        calendar = load_trading_calendar(paths.root)
        monthly_calendar = build_monthly_calendar(calendar, start_month=start_month, end_month=end_month)
        instruments = load_instruments(paths.root)
        pit = load_partitioned_dataset(paths.root / "financial_pit_quarterly")
        rf = load_partitioned_dataset(paths.root / "risk_free_rate")
        prices_pre = load_partitioned_dataset(paths.root / "prices_1d_pre")
        valuation = load_partitioned_dataset(paths.root / "valuation_1d")
        tradability = load_partitioned_dataset(paths.root / "tradability_1d")
        industry = load_partitioned_dataset(paths.root / "industry_classification")

        monthly_returns = compute_monthly_returns(prices_pre, monthly_calendar)
        lagged_market_cap = compute_lagged_market_cap(valuation, monthly_calendar)
        june_market_cap = compute_june_market_cap(valuation, monthly_calendar)
        monthly_rf = compute_monthly_rf(rf, monthly_calendar)
        monthly_tradability = compute_monthly_tradability(tradability, monthly_calendar)
        monthly_industry = compute_monthly_industry(industry, monthly_calendar)
        quarterly_roe = compute_monthly_quarterly_roe(pit, monthly_calendar)
        annual_ia = compute_monthly_annual_ia(pit, monthly_calendar)

        panel = assemble_panel(
            monthly_calendar=monthly_calendar,
            instruments=instruments,
            monthly_returns=monthly_returns,
            lagged_market_cap=lagged_market_cap,
            june_market_cap=june_market_cap,
            monthly_rf=monthly_rf,
            monthly_tradability=monthly_tradability,
            monthly_industry=monthly_industry,
            quarterly_roe=quarterly_roe,
            annual_ia=annual_ia,
        )
        quality = check_hxz_monthly_panel(panel, monthly_calendar, quarterly_roe, annual_ia)
        outputs = write_hxz_p1_outputs(
            paths=paths,
            monthly_calendar=monthly_calendar,
            panel=panel,
            quarterly_roe=quarterly_roe,
            annual_ia=annual_ia,
            monthly_rf=monthly_rf,
            quality=quality,
        )
        report = build_hxz_p1_report(
            run_id=run_id,
            status="success" if quality["error_count"] == 0 else "failed",
            started_at=started_at,
            outputs=outputs,
            panel=panel,
            monthly_calendar=monthly_calendar,
            quarterly_roe=quarterly_roe,
            annual_ia=annual_ia,
            quality=quality,
        )
        write_hxz_p1_reports(report, report_dir=report_dir)
        append_hxz_p1_status(
            paths.status_path,
            {
                "run_id": run_id,
                "created_at": started_at,
                "dataset": PANEL_DATASET,
                "start_month": str(monthly_calendar["month"].min()),
                "end_month": str(monthly_calendar["month"].max()),
                "status": report["status"],
                "row_count": len(panel),
                "output_files": ";".join(str(path) for path in outputs.values()),
                "error": "",
            },
        )
        return report
    except Exception as exc:
        append_hxz_p1_status(
            paths.status_path,
            {
                "run_id": run_id,
                "created_at": started_at,
                "dataset": PANEL_DATASET,
                "start_month": start_month or "",
                "end_month": end_month or "",
                "status": "failed",
                "row_count": 0,
                "output_files": "",
                "error": f"{type(exc).__name__}: {exc}",
            },
        )
        raise


def build_monthly_calendar(
    calendar: pd.DataFrame,
    *,
    start_month: str | None = None,
    end_month: str | None = None,
) -> pd.DataFrame:
    frame = calendar.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(bool)]
    frame = frame.sort_values("trade_date").reset_index(drop=True)
    frame["month"] = frame["trade_date"].dt.to_period("M").astype(str)
    months = sorted(frame["month"].unique().tolist())
    if start_month:
        months = [month for month in months if month >= start_month]
    if end_month:
        months = [month for month in months if month <= end_month]
    records: list[dict[str, Any]] = []
    all_dates = frame["trade_date"].tolist()
    for month in months:
        month_dates = frame.loc[frame["month"].eq(month), "trade_date"].tolist()
        if not month_dates:
            continue
        formation = month_dates[0]
        previous_candidates = [date for date in all_dates if date < formation]
        if not previous_candidates:
            continue
        prev_trade = previous_candidates[-1]
        month_end = month_dates[-1]
        prev_month = (pd.Period(month, freq="M") - 1).strftime("%Y-%m")
        prev_month_dates = frame.loc[frame["month"].eq(prev_month), "trade_date"].tolist()
        if not prev_month_dates:
            continue
        records.append(
            {
                "month": month,
                "formation_date": formation.strftime("%Y-%m-%d"),
                "previous_trade_date": prev_trade.strftime("%Y-%m-%d"),
                "month_end_date": month_end.strftime("%Y-%m-%d"),
                "previous_month_end_date": prev_month_dates[-1].strftime("%Y-%m-%d"),
                "expected_trading_days": len(month_dates),
                "holding_calendar_days": int((month_end - formation).days + 1),
            }
        )
    return pd.DataFrame(records)


def select_pit_asof(financials: pd.DataFrame, formation_date: str) -> pd.DataFrame:
    frame = financials.copy()
    frame["info_date"] = pd.to_datetime(frame["info_date"], errors="coerce")
    frame["rice_create_tm"] = pd.to_datetime(frame["rice_create_tm"], errors="coerce")
    visible = frame[frame["info_date"] < pd.Timestamp(formation_date)].copy()
    if visible.empty:
        return visible
    visible = visible.sort_values(["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"])
    selected = visible.groupby(["order_book_id", "quarter"], as_index=False).tail(1).copy()
    selected["formation_date"] = pd.Timestamp(formation_date).strftime("%Y-%m-%d")
    selected["selected_info_date"] = selected["info_date"].dt.strftime("%Y-%m-%d")
    selected["selected_rice_create_tm"] = selected["rice_create_tm"].dt.strftime("%Y-%m-%d %H:%M:%S")
    selected["selected_if_adjusted"] = selected["if_adjusted"]
    counts = visible.groupby(["order_book_id", "quarter"]).size().rename("version_count_available").reset_index()
    selected = selected.merge(counts, on=["order_book_id", "quarter"], how="left")
    selected["financial_age_days"] = (
        pd.Timestamp(formation_date) - pd.to_datetime(selected["selected_info_date"], errors="coerce")
    ).dt.days
    return selected.reset_index(drop=True)


def derive_single_quarter_profit(selected: pd.DataFrame) -> pd.DataFrame:
    frame = selected.copy()
    if frame.empty:
        return frame
    if "selected_info_date" not in frame.columns:
        frame["selected_info_date"] = pd.NA
    frame["quarter_year"] = frame["quarter"].astype(str).str[:4].astype(int)
    frame["quarter_num"] = frame["quarter"].astype(str).str[-1].astype(int)
    frame["net_profit_parent_company_cumulative"] = pd.to_numeric(frame["net_profit_parent_company"], errors="coerce")
    previous = frame[
        [
            "order_book_id",
            "quarter_year",
            "quarter_num",
            "net_profit_parent_company_cumulative",
            "selected_info_date",
        ]
    ].copy()
    previous["quarter_num"] += 1
    previous = previous.rename(
        columns={
            "net_profit_parent_company_cumulative": "previous_cumulative_profit",
            "selected_info_date": "previous_profit_info_date",
        }
    )
    out = frame.merge(previous, on=["order_book_id", "quarter_year", "quarter_num"], how="left")
    q1 = out["quarter_num"].eq(1)
    out["single_quarter_parent_profit"] = out["net_profit_parent_company_cumulative"] - out["previous_cumulative_profit"]
    out.loc[q1, "single_quarter_parent_profit"] = out.loc[q1, "net_profit_parent_company_cumulative"]
    out["single_quarter_conversion_status"] = "ok"
    out.loc[out["net_profit_parent_company_cumulative"].isna(), "single_quarter_conversion_status"] = "missing_current_profit"
    out.loc[~q1 & out["previous_cumulative_profit"].isna(), "single_quarter_conversion_status"] = "missing_previous_cumulative"
    out.loc[out["single_quarter_parent_profit"].isna(), "single_quarter_conversion_status"] = out.loc[
        out["single_quarter_parent_profit"].isna(), "single_quarter_conversion_status"
    ].replace("ok", "conversion_failed")
    out["current_profit_info_date"] = out["selected_info_date"]
    return out


def compute_roe_from_selected(selected: pd.DataFrame, formation_date: str, month: str) -> pd.DataFrame:
    profits = derive_single_quarter_profit(selected)
    if profits.empty:
        return profits
    denom = selected[["order_book_id", "quarter", "equity_parent_company", "total_equity", "selected_info_date"]].copy()
    denom["quarter"] = denom["quarter"].map(next_quarter)
    denom = denom.rename(
        columns={
            "equity_parent_company": "book_equity_previous_quarter",
            "total_equity": "total_equity_previous_quarter",
            "selected_info_date": "book_equity_info_date",
        }
    )
    out = profits.merge(
        denom[[
            "order_book_id",
            "quarter",
            "book_equity_previous_quarter",
            "total_equity_previous_quarter",
            "book_equity_info_date",
        ]],
        on=["order_book_id", "quarter"],
        how="left",
    )
    book = pd.to_numeric(out["book_equity_previous_quarter"], errors="coerce")
    total = pd.to_numeric(out["total_equity_previous_quarter"], errors="coerce")
    profit = pd.to_numeric(out["single_quarter_parent_profit"], errors="coerce")
    out["positive_book_equity"] = book > 0
    out["book_equity_source"] = "equity_parent_company"
    out.loc[book.isna(), "book_equity_source"] = "missing"
    out["roe_primary"] = profit / book
    out.loc[~out["positive_book_equity"], "roe_primary"] = pd.NA
    out["roe_total_equity_fallback"] = profit / total
    out.loc[total <= 0, "roe_total_equity_fallback"] = pd.NA
    out["roe"] = out["roe_primary"]
    out["roe_report_quarter"] = out["quarter"]
    out["roe_info_date"] = out["selected_info_date"]
    out["roe_age_days"] = (pd.Timestamp(formation_date) - pd.to_datetime(out["roe_info_date"], errors="coerce")).dt.days
    out["roe_is_stale"] = out["roe_age_days"] > 183
    out["has_valid_roe"] = out["roe"].notna() & ~out["roe_is_stale"]
    out["month"] = month
    out["formation_date"] = formation_date
    return out


def compute_monthly_quarterly_roe(financials: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, cal in monthly_calendar.iterrows():
        selected = select_pit_asof(financials, cal["formation_date"])
        roe_rows = compute_roe_from_selected(selected, cal["formation_date"], cal["month"])
        if roe_rows.empty:
            continue
        valid_or_latest = roe_rows.sort_values(["order_book_id", "quarter"])
        latest = valid_or_latest.groupby("order_book_id", as_index=False).tail(1)
        records.append(latest)
    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


def compute_monthly_annual_ia(financials: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    records = []
    for _, cal in monthly_calendar.iterrows():
        selected = select_pit_asof(financials, cal["formation_date"])
        if selected.empty:
            continue
        month_period = pd.Period(cal["month"], freq="M")
        ia_formation_year = month_period.year if month_period.month >= 7 else month_period.year - 1
        current_fy = ia_formation_year - 1
        prior_fy = ia_formation_year - 2
        q4 = selected[selected["quarter"].astype(str).str.endswith("q4")].copy()
        current = q4[q4["quarter"].eq(f"{current_fy}q4")][
            ["order_book_id", "total_assets", "selected_info_date"]
        ].rename(columns={"total_assets": "total_assets_current_fy", "selected_info_date": "current_assets_info_date"})
        prior = q4[q4["quarter"].eq(f"{prior_fy}q4")][
            ["order_book_id", "total_assets", "selected_info_date"]
        ].rename(columns={"total_assets": "total_assets_prior_fy", "selected_info_date": "prior_assets_info_date"})
        ia = current.merge(prior, on="order_book_id", how="outer")
        ia["month"] = cal["month"]
        ia["formation_date"] = cal["formation_date"]
        ia["ia_formation_year"] = ia_formation_year
        ia["current_fy"] = current_fy
        ia["prior_fy"] = prior_fy
        ia["ia_effective_start"] = f"{ia_formation_year}-07"
        ia["ia_effective_end"] = f"{ia_formation_year + 1}-06"
        current_assets = pd.to_numeric(ia["total_assets_current_fy"], errors="coerce")
        prior_assets = pd.to_numeric(ia["total_assets_prior_fy"], errors="coerce")
        ia["ia"] = (current_assets - prior_assets) / prior_assets
        ia["ia_valid"] = ia["ia"].notna() & (prior_assets > 0)
        ia["has_valid_ia"] = ia["ia_valid"]
        ia["ia_missing_reason"] = ""
        ia.loc[current_assets.isna(), "ia_missing_reason"] = "missing_current_fy_assets"
        ia.loc[prior_assets.isna(), "ia_missing_reason"] = "missing_prior_fy_assets"
        ia.loc[prior_assets <= 0, "ia_missing_reason"] = "non_positive_prior_assets"
        records.append(ia)
    if not records:
        return pd.DataFrame()
    return pd.concat(records, ignore_index=True)


def compute_monthly_returns(prices: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    frame = prices.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["close"] = pd.to_numeric(frame["close"], errors="coerce")
    lookup = frame[["trade_date", "order_book_id", "close"]]
    out = []
    for _, cal in monthly_calendar.iterrows():
        start = pd.Timestamp(cal["formation_date"])
        end = pd.Timestamp(cal["month_end_date"])
        prev_end = pd.Timestamp(cal["previous_month_end_date"])
        month_prices = lookup[(lookup["trade_date"] >= start) & (lookup["trade_date"] <= end)]
        coverage = month_prices.groupby("order_book_id").agg(
            trading_days_in_month=("trade_date", "nunique"),
            first_valid_trade_date=("trade_date", "min"),
            last_valid_trade_date=("trade_date", "max"),
        )
        month_end = lookup[lookup["trade_date"].eq(end)][["order_book_id", "close"]].rename(columns={"close": "month_end_close_pre"})
        prev = lookup[lookup["trade_date"].eq(prev_end)][["order_book_id", "close"]].rename(columns={"close": "previous_month_end_close_pre"})
        result = month_end.merge(prev, on="order_book_id", how="outer").merge(coverage, on="order_book_id", how="left")
        result["month"] = cal["month"]
        result["expected_trading_days"] = cal["expected_trading_days"]
        result["monthly_return"] = result["month_end_close_pre"] / result["previous_month_end_close_pre"] - 1
        result["return_coverage"] = result["trading_days_in_month"] / cal["expected_trading_days"]
        result["suspended_days"] = cal["expected_trading_days"] - result["trading_days_in_month"].fillna(0)
        result["return_valid"] = result["monthly_return"].notna() & (result["return_coverage"] >= 0.8)
        for col in ["first_valid_trade_date", "last_valid_trade_date"]:
            result[col] = pd.to_datetime(result[col], errors="coerce").dt.strftime("%Y-%m-%d")
        out.append(result)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


def compute_lagged_market_cap(valuation: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    frame = valuation.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    records = []
    for _, cal in monthly_calendar.iterrows():
        day = frame[frame["trade_date"].eq(pd.Timestamp(cal["previous_month_end_date"]))].copy()
        day = day[["order_book_id", "market_cap", "float_market_cap", "trade_date"]]
        day = day.rename(columns={"market_cap": "market_cap_lag", "float_market_cap": "float_market_cap_lag", "trade_date": "market_cap_date"})
        day["month"] = cal["month"]
        day["market_cap_date"] = pd.to_datetime(day["market_cap_date"]).dt.strftime("%Y-%m-%d")
        records.append(day)
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def compute_june_market_cap(valuation: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    frame = valuation.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    records = []
    for _, cal in monthly_calendar.iterrows():
        period = pd.Period(cal["month"], freq="M")
        size_year = period.year if period.month >= 7 else period.year - 1
        june_dates = frame[(frame["trade_date"].dt.year == size_year) & (frame["trade_date"].dt.month == 6)]["trade_date"]
        if june_dates.empty:
            continue
        june_date = june_dates.max()
        day = frame[frame["trade_date"].eq(june_date)][["order_book_id", "market_cap", "trade_date"]].copy()
        day = day.rename(columns={"market_cap": "june_market_cap", "trade_date": "june_market_cap_date"})
        day["month"] = cal["month"]
        day["size_formation_year"] = size_year
        day["june_market_cap_date"] = pd.to_datetime(day["june_market_cap_date"]).dt.strftime("%Y-%m-%d")
        records.append(day)
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def compute_monthly_rf(rf: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    frame = rf.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    frame["1M"] = pd.to_numeric(frame["1M"], errors="coerce")
    records = []
    for _, cal in monthly_calendar.iterrows():
        visible = frame[frame["trade_date"] < pd.Timestamp(cal["formation_date"])]
        if visible.empty:
            row = {"rf_source_date": pd.NA, "rf_1m_annual": pd.NA}
        else:
            latest = visible.sort_values("trade_date").tail(1).iloc[0]
            row = {"rf_source_date": latest["trade_date"].strftime("%Y-%m-%d"), "rf_1m_annual": latest["1M"]}
        annual = row["rf_1m_annual"]
        row["month"] = cal["month"]
        row["formation_date"] = cal["formation_date"]
        row["rf_monthly"] = (1 + annual) ** (cal["holding_calendar_days"] / 365) - 1 if pd.notna(annual) else pd.NA
        row["rf_monthly_1_over_12"] = (1 + annual) ** (1 / 12) - 1 if pd.notna(annual) else pd.NA
        row["rf_staleness_days"] = (
            (pd.Timestamp(cal["formation_date"]) - pd.Timestamp(row["rf_source_date"])).days if pd.notna(row["rf_source_date"]) else pd.NA
        )
        records.append(row)
    return pd.DataFrame(records)


def compute_monthly_tradability(tradability: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    frame = tradability.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    records = []
    for _, cal in monthly_calendar.iterrows():
        formation = frame[frame["trade_date"].eq(pd.Timestamp(cal["formation_date"]))].copy()
        formation = formation[["order_book_id", "is_listed", "is_suspended", "is_st", "can_buy", "can_sell"]]
        formation["month"] = cal["month"]
        records.append(formation)
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def compute_monthly_industry(industry: pd.DataFrame, monthly_calendar: pd.DataFrame) -> pd.DataFrame:
    frame = industry.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"])
    records = []
    for _, cal in monthly_calendar.iterrows():
        day = frame[frame["trade_date"].eq(pd.Timestamp(cal["formation_date"]))].copy()
        day = day[["order_book_id", "industry_code", "industry_name"]]
        day["month"] = cal["month"]
        records.append(day)
    return pd.concat(records, ignore_index=True) if records else pd.DataFrame()


def assemble_panel(
    *,
    monthly_calendar: pd.DataFrame,
    instruments: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    lagged_market_cap: pd.DataFrame,
    june_market_cap: pd.DataFrame,
    monthly_rf: pd.DataFrame,
    monthly_tradability: pd.DataFrame,
    monthly_industry: pd.DataFrame,
    quarterly_roe: pd.DataFrame,
    annual_ia: pd.DataFrame,
) -> pd.DataFrame:
    panel = monthly_returns.merge(monthly_calendar, on=["month", "expected_trading_days"], how="left")
    for other in [lagged_market_cap, june_market_cap, monthly_rf.drop(columns=["formation_date"], errors="ignore")]:
        panel = _merge_optional(panel, other, on="month" if "order_book_id" not in other.columns else ["month", "order_book_id"])
    panel = _merge_optional(panel, monthly_tradability, on=["month", "order_book_id"])
    panel = _merge_optional(panel, monthly_industry, on=["month", "order_book_id"])
    panel = _merge_optional(
        panel,
        quarterly_roe[
            [
                "month",
                "order_book_id",
                "roe",
                "roe_primary",
                "roe_total_equity_fallback",
                "roe_report_quarter",
                "roe_info_date",
                "roe_age_days",
                "roe_is_stale",
                "has_valid_roe",
                "positive_book_equity",
                "book_equity_source",
                "book_equity_previous_quarter",
                "book_equity_info_date",
                "single_quarter_parent_profit",
                "single_quarter_conversion_status",
                "current_profit_info_date",
                "previous_profit_info_date",
                "selected_rice_create_tm",
                "selected_if_adjusted",
                "version_count_available",
            ]
        ],
        on=["month", "order_book_id"],
    )
    panel = _merge_optional(
        panel,
        annual_ia[
            [
                "month",
                "order_book_id",
                "ia",
                "ia_valid",
                "has_valid_ia",
                "ia_formation_year",
                "ia_effective_start",
                "ia_effective_end",
                "total_assets_current_fy",
                "total_assets_prior_fy",
                "current_assets_info_date",
                "prior_assets_info_date",
                "ia_missing_reason",
                "current_fy",
                "prior_fy",
            ]
        ],
        on=["month", "order_book_id"],
    )
    inst = instruments.copy()
    inst = inst[["order_book_id", "type", "listed_date", "de_listed_date", "status", "special_type", "sector_code_name", "sector_code", "board_type"]]
    panel = panel.merge(inst, on="order_book_id", how="left")
    panel["is_common_a_share"] = panel["type"].astype(str).eq("CS")
    panel["listed_date_ts"] = pd.to_datetime(panel["listed_date"], errors="coerce")
    panel["de_listed_date_ts"] = pd.to_datetime(panel["de_listed_date"], errors="coerce")
    formation = pd.to_datetime(panel["formation_date"], errors="coerce")
    panel["is_listed"] = panel["is_listed"].fillna(
        panel["listed_date_ts"].notna() & (panel["listed_date_ts"] <= formation) & (panel["de_listed_date_ts"].isna() | (panel["de_listed_date_ts"] >= formation))
    )
    panel["is_delisted"] = panel["de_listed_date_ts"].notna() & (panel["de_listed_date_ts"] < formation)
    panel["is_st"] = panel["is_st"].fillna(panel["special_type"].astype(str).str.contains("ST", case=False, na=False))
    panel["is_suspended"] = panel["is_suspended"].fillna(False)
    panel["is_financial"] = (
        panel["sector_code_name"].astype(str).isin(FINANCIAL_SECTOR_NAMES)
        | panel["sector_code"].astype(str).eq("Financials")
        | panel["industry_name"].astype(str).str.contains("|".join(FINANCIAL_INDUSTRY_KEYWORDS), na=False)
    )
    panel["market_cap_lag"] = pd.to_numeric(panel["market_cap_lag"], errors="coerce")
    panel["float_market_cap_lag"] = pd.to_numeric(panel["float_market_cap_lag"], errors="coerce")
    panel["has_valid_market_cap"] = panel["market_cap_lag"].notna() & (panel["market_cap_lag"] > 0)
    panel["has_valid_return"] = panel["return_valid"].fillna(False)
    panel["positive_book_equity"] = panel["positive_book_equity"].fillna(False)
    panel["has_valid_ia"] = panel["has_valid_ia"].fillna(False)
    panel["has_valid_roe"] = panel["has_valid_roe"].fillna(False)
    panel["excess_return"] = panel["monthly_return"] - panel["rf_monthly"]
    panel["eligible_hxz_academic"] = (
        panel["is_common_a_share"].fillna(False)
        & panel["is_listed"].fillna(False)
        & ~panel["is_delisted"].fillna(False)
        & ~panel["is_financial"].fillna(False)
        & panel["positive_book_equity"].fillna(False)
        & panel["has_valid_return"].fillna(False)
        & panel["has_valid_market_cap"].fillna(False)
        & panel["has_valid_ia"].fillna(False)
        & panel["has_valid_roe"].fillna(False)
    )
    panel["eligible_hxz_tradable"] = panel["eligible_hxz_academic"] & ~panel["is_st"].fillna(False) & ~panel["is_suspended"].fillna(False)
    panel = panel.drop(columns=["listed_date_ts", "de_listed_date_ts"], errors="ignore")
    for column in [
        "june_market_cap",
        "june_market_cap_date",
        "size_formation_year",
        "industry_code",
        "industry_name",
    ]:
        if column not in panel.columns:
            panel[column] = pd.NA
    return panel.sort_values(["month", "order_book_id"]).reset_index(drop=True)


def _merge_optional(left: pd.DataFrame, right: pd.DataFrame, *, on: str | list[str]) -> pd.DataFrame:
    keys = [on] if isinstance(on, str) else on
    if right.empty or not set(keys).issubset(right.columns):
        return left
    return left.merge(right, on=on, how="left")


def check_hxz_monthly_panel(
    panel: pd.DataFrame,
    monthly_calendar: pd.DataFrame,
    quarterly_roe: pd.DataFrame,
    annual_ia: pd.DataFrame,
) -> dict[str, Any]:
    issues = []
    duplicate_key = int(panel.duplicated(["month", "order_book_id"]).sum()) if not panel.empty else 0
    if duplicate_key:
        issues.append({"severity": "error", "check": "panel_primary_key", "count": duplicate_key})
    months = sorted(monthly_calendar["month"].astype(str).unique().tolist())
    expected = pd.period_range(months[0], months[-1], freq="M").astype(str).tolist() if months else []
    missing_months = sorted(set(expected) - set(months))
    if missing_months:
        issues.append({"severity": "error", "check": "month_continuity", "count": len(missing_months), "sample": missing_months[:10]})
    no_lookahead_roe = int((pd.to_datetime(panel["roe_info_date"], errors="coerce") >= pd.to_datetime(panel["formation_date"], errors="coerce")).sum())
    no_lookahead_ia_current = int((pd.to_datetime(panel["current_assets_info_date"], errors="coerce") >= pd.to_datetime(panel["formation_date"], errors="coerce")).sum())
    no_lookahead_ia_prior = int((pd.to_datetime(panel["prior_assets_info_date"], errors="coerce") >= pd.to_datetime(panel["formation_date"], errors="coerce")).sum())
    for name, count in {
        "roe_info_date_before_formation": no_lookahead_roe,
        "ia_current_info_date_before_formation": no_lookahead_ia_current,
        "ia_prior_info_date_before_formation": no_lookahead_ia_prior,
    }.items():
        if count:
            issues.append({"severity": "error", "check": name, "count": count})
    stale_valid = int((panel["has_valid_roe"].fillna(False) & panel["roe_is_stale"].fillna(False)).sum())
    if stale_valid:
        issues.append({"severity": "error", "check": "stale_roe_marked_valid", "count": stale_valid})
    ia_non_q4 = int((annual_ia["current_fy"].isna() | annual_ia["prior_fy"].isna()).sum()) if not annual_ia.empty else 0
    conversion_failures = (
        quarterly_roe["single_quarter_conversion_status"].fillna("missing").value_counts().to_dict() if not quarterly_roe.empty else {}
    )
    extreme_returns = int((pd.to_numeric(panel["monthly_return"], errors="coerce").abs() > 3).sum())
    if extreme_returns:
        issues.append({"severity": "warning", "check": "monthly_return_abs_gt_300pct", "count": extreme_returns})
    market_cap_dates = pd.to_datetime(panel["market_cap_date"], errors="coerce")
    previous_month_end_dates = pd.to_datetime(panel["previous_month_end_date"], errors="coerce")
    market_cap_date_bad = int((market_cap_dates.notna() & market_cap_dates.ne(previous_month_end_dates)).sum())
    if market_cap_date_bad:
        issues.append({"severity": "error", "check": "market_cap_from_previous_month_end", "count": market_cap_date_bad})
    return {
        "issues": issues,
        "error_count": int(sum(1 for issue in issues if issue["severity"] == "error")),
        "warning_count": int(sum(1 for issue in issues if issue["severity"] == "warning")),
        "duplicate_key": duplicate_key,
        "missing_months": missing_months,
        "no_lookahead_violations": no_lookahead_roe + no_lookahead_ia_current + no_lookahead_ia_prior,
        "single_quarter_conversion_status": {str(k): int(v) for k, v in conversion_failures.items()},
        "ia_non_q4_proxy_count": ia_non_q4,
        "monthly_return_abs_gt_300pct": extreme_returns,
    }


def build_hxz_p1_report(
    *,
    run_id: str,
    status: str,
    started_at: str,
    outputs: dict[str, Path],
    panel: pd.DataFrame,
    monthly_calendar: pd.DataFrame,
    quarterly_roe: pd.DataFrame,
    annual_ia: pd.DataFrame,
    quality: dict[str, Any],
) -> dict[str, Any]:
    coverage = {
        "monthly_return": _coverage(panel, "monthly_return"),
        "market_cap_lag": _coverage(panel, "market_cap_lag"),
        "ia": _coverage(panel, "ia"),
        "roe": _coverage(panel, "roe"),
        "rf_monthly": _coverage(panel, "rf_monthly"),
        "eligible_hxz_academic": round(float(panel["eligible_hxz_academic"].mean()), 6) if len(panel) else 0.0,
    }
    eligible = panel.groupby("month")["eligible_hxz_academic"].sum().astype(int).to_dict() if not panel.empty else {}
    sample = panel.sort_values(["month", "order_book_id"]).head(20)
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "rows": int(len(panel)),
        "symbols": int(panel["order_book_id"].nunique()) if not panel.empty else 0,
        "months": int(panel["month"].nunique()) if not panel.empty else 0,
        "date_range": {
            "start_month": str(monthly_calendar["month"].min()) if not monthly_calendar.empty else None,
            "end_month": str(monthly_calendar["month"].max()) if not monthly_calendar.empty else None,
            "formation_start": str(monthly_calendar["formation_date"].min()) if not monthly_calendar.empty else None,
            "formation_end": str(monthly_calendar["formation_date"].max()) if not monthly_calendar.empty else None,
        },
        "coverage": coverage,
        "eligible_hxz_academic_by_month": {str(k): int(v) for k, v in eligible.items()},
        "single_quarter_conversion_status": quality["single_quarter_conversion_status"],
        "no_lookahead_violations": quality["no_lookahead_violations"],
        "quality": quality,
        "roe": {
            "rows": int(len(quarterly_roe)),
            "report_quarters": int(quarterly_roe["roe_report_quarter"].nunique()) if not quarterly_roe.empty else 0,
        },
        "ia": {
            "rows": int(len(annual_ia)),
            "formation_years": int(annual_ia["ia_formation_year"].nunique()) if not annual_ia.empty else 0,
        },
        "sample_audit_20": sample[
            [
                "month",
                "formation_date",
                "order_book_id",
                "monthly_return",
                "market_cap_lag",
                "ia",
                "roe",
                "roe_info_date",
                "current_assets_info_date",
                "prior_assets_info_date",
                "eligible_hxz_academic",
            ]
        ].to_dict("records"),
        "outputs": {key: str(path) for key, path in outputs.items()},
    }


def write_hxz_p1_outputs(
    *,
    paths: HXZP1Paths,
    monthly_calendar: pd.DataFrame,
    panel: pd.DataFrame,
    quarterly_roe: pd.DataFrame,
    annual_ia: pd.DataFrame,
    monthly_rf: pd.DataFrame,
    quality: dict[str, Any],
) -> dict[str, Path]:
    paths.output_root.mkdir(parents=True, exist_ok=True)
    outputs = {
        "panel": paths.output_root / "hxz_monthly_research_panel.parquet",
        "monthly_calendar": paths.output_root / "hxz_monthly_calendar.parquet",
        "annual_ia": paths.output_root / "hxz_annual_ia.parquet",
        "quarterly_roe": paths.output_root / "hxz_quarterly_roe.parquet",
        "monthly_rf": paths.output_root / "hxz_monthly_rf.parquet",
        "manifest": paths.manifest_path,
    }
    for frame, path in [
        (panel, outputs["panel"]),
        (monthly_calendar, outputs["monthly_calendar"]),
        (annual_ia, outputs["annual_ia"]),
        (quarterly_roe, outputs["quarterly_roe"]),
        (monthly_rf, outputs["monthly_rf"]),
    ]:
        atomic_write_parquet(frame, path)
    manifest = {
        "dataset": PANEL_DATASET,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "outputs": {key: str(value) for key, value in outputs.items() if key != "manifest"},
        "rows": int(len(panel)),
        "symbols": int(panel["order_book_id"].nunique()) if not panel.empty else 0,
        "months": int(panel["month"].nunique()) if not panel.empty else 0,
        "quality": quality,
        "checksums": {key: checksum_file(path) for key, path in outputs.items() if key != "manifest" and path.exists()},
    }
    outputs["manifest"].parent.mkdir(parents=True, exist_ok=True)
    outputs["manifest"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return outputs


def write_hxz_p1_reports(report: dict[str, Any], *, report_dir: str | Path = REPORT_DIR) -> dict[str, Path]:
    output = Path(report_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = {
        "summary": output / "hxz_p1_monthly_panel.md",
        "financial": output / "hxz_p1_financial_derivation.md",
        "lookahead": output / "hxz_p1_no_lookahead_validation.md",
        "coverage": output / "hxz_p1_coverage.md",
        "json": output / "hxz_p1_monthly_panel.json",
    }
    paths["json"].write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths["summary"].write_text(render_summary_markdown(report), encoding="utf-8")
    paths["financial"].write_text(render_financial_markdown(report), encoding="utf-8")
    paths["lookahead"].write_text(render_lookahead_markdown(report), encoding="utf-8")
    paths["coverage"].write_text(render_coverage_markdown(report), encoding="utf-8")
    return paths


def append_hxz_p1_status(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: record.get(column, "") for column in STATUS_COLUMNS}
    pd.DataFrame([row], columns=STATUS_COLUMNS).to_csv(path, mode="a", header=not path.exists(), index=False)


def load_trading_calendar(root: Path) -> pd.DataFrame:
    return pd.read_parquet(root / "trading_calendar" / "trading_calendar.parquet")


def load_instruments(root: Path) -> pd.DataFrame:
    return pd.read_parquet(root / "instruments" / "instruments.parquet")


def load_partitioned_dataset(path: Path) -> pd.DataFrame:
    files = sorted(path.glob("year=*.parquet"))
    if not files:
        raise FileNotFoundError(f"No year partitions found under {path}")
    return pd.concat([pd.read_parquet(file) for file in files], ignore_index=True)


def atomic_write_parquet(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    frame.to_parquet(tmp, index=False)
    verify = pd.read_parquet(tmp)
    if len(verify) != len(frame):
        tmp.unlink(missing_ok=True)
        raise ValueError(f"atomic parquet verification failed for {path}")
    tmp.replace(path)


def next_quarter(quarter: str) -> str:
    year = int(str(quarter)[:4])
    q = int(str(quarter)[-1])
    if q == 4:
        return f"{year + 1}q1"
    return f"{year}q{q + 1}"


def _paths(data_root: str | Path | None, output_dir: str | Path | None) -> HXZP1Paths:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    output_root = Path(output_dir).resolve() if output_dir is not None else root / PANEL_DATASET
    return HXZP1Paths(
        root=root,
        output_root=output_root,
        status_path=root / "update_logs" / "hxz_p1_monthly_panel_status.csv",
        manifest_path=root / "manifests" / "hxz_p1_monthly_panel_manifest.json",
    )


def _coverage(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return round(float(frame[column].notna().mean()), 6)


def checksum_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.name.encode())
    h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def render_summary_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# HXZ P1 Monthly Research Panel",
        "",
        f"- status: {report['status']}",
        f"- rows: {report['rows']}",
        f"- symbols: {report['symbols']}",
        f"- months: {report['months']}",
        f"- date_range: {report['date_range']}",
        f"- no_lookahead_violations: {report['no_lookahead_violations']}",
        f"- quality_errors: {report['quality']['error_count']}",
        f"- quality_warnings: {report['quality']['warning_count']}",
        "",
        "## Outputs",
    ]
    for key, value in report["outputs"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def render_financial_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HXZ P1 Financial Derivation",
            "",
            f"- quarterly_roe_rows: {report['roe']['rows']}",
            f"- roe_report_quarters: {report['roe']['report_quarters']}",
            f"- annual_ia_rows: {report['ia']['rows']}",
            f"- ia_formation_years: {report['ia']['formation_years']}",
            f"- single_quarter_conversion_status: {report['single_quarter_conversion_status']}",
            "",
            "Rules: info_date must be strictly before formation_date; same-day announcements are not treated as known at open.",
        ]
    ) + "\n"


def render_lookahead_markdown(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# HXZ P1 No Lookahead Validation",
            "",
            f"- no_lookahead_violations: {report['no_lookahead_violations']}",
            f"- issues: {report['quality']['issues']}",
            "",
            "PIT selection uses info_date < formation_date.",
        ]
    ) + "\n"


def render_coverage_markdown(report: dict[str, Any]) -> str:
    lines = ["# HXZ P1 Coverage", ""]
    for key, value in report["coverage"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Eligible Academic Count By Month", ""])
    for month, count in report["eligible_hxz_academic_by_month"].items():
        lines.append(f"- {month}: {count}")
    return "\n".join(lines) + "\n"
