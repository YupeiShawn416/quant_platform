from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

PIT_FIELDS = ["total_assets", "equity_parent_company", "total_equity", "net_profit_parent_company"]
FACTOR_FIELDS = [
    "total_assets_mrq_0",
    "total_assets_lyr_0",
    "equity_parent_company_mrq_0",
    "equity_parent_company_lyr_0",
    "total_equity_mrq_0",
    "net_profit_parent_company_mrq_0",
    "net_profit_parent_company_lyr_0",
]
RISK_FREE_FIELDS = ["0S", "1M", "3M", "1Y"]


@dataclass(frozen=True)
class HXZQualityIssue:
    dataset: str
    severity: str
    check: str
    message: str
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def check_financial_pit_quarterly(frame: pd.DataFrame) -> list[HXZQualityIssue]:
    issues: list[HXZQualityIssue] = []
    required = ["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"] + PIT_FIELDS
    issues.extend(_required_columns("financial_pit_quarterly", frame, required))
    if issues:
        return issues
    quarter_ok = frame["quarter"].astype(str).str.match(r"^\d{4}q[1-4]$").fillna(False)
    if not quarter_ok.all():
        issues.append(HXZQualityIssue("financial_pit_quarterly", "error", "quarter_format", "invalid quarter values", int((~quarter_ok).sum())))
    info_dates = pd.to_datetime(frame["info_date"], errors="coerce")
    bad_info_date = int(info_dates.isna().sum())
    if bad_info_date:
        issues.append(HXZQualityIssue("financial_pit_quarterly", "error", "info_date_format", "unparseable info_date", bad_info_date))
    duplicate_key = int(frame.duplicated(["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"]).sum())
    if duplicate_key:
        issues.append(HXZQualityIssue("financial_pit_quarterly", "error", "candidate_key_unique", "duplicate raw PIT version keys", duplicate_key))
    multi_versions = int(frame.duplicated(["order_book_id", "quarter"], keep=False).sum())
    if multi_versions:
        issues.append(HXZQualityIssue("financial_pit_quarterly", "warning", "multi_version", "multiple PIT versions detected and should be retained", multi_versions))
    for field in PIT_FIELDS:
        values = pd.to_numeric(frame[field], errors="coerce")
        if values.notna().sum() == 0:
            issues.append(HXZQualityIssue("financial_pit_quarterly", "error", f"{field}_coverage", f"{field} has no numeric coverage", len(frame)))
    if (pd.to_numeric(frame["total_assets"], errors="coerce") <= 0).any():
        issues.append(HXZQualityIssue("financial_pit_quarterly", "error", "total_assets_positive", "total_assets must be positive", int((pd.to_numeric(frame["total_assets"], errors="coerce") <= 0).sum())))
    return issues


def check_financial_factor_daily_pit(frame: pd.DataFrame) -> list[HXZQualityIssue]:
    issues: list[HXZQualityIssue] = []
    required = ["trade_date", "order_book_id"] + FACTOR_FIELDS
    issues.extend(_required_columns("financial_factor_daily_pit", frame, required))
    if issues:
        return issues
    duplicate_key = int(frame.duplicated(["trade_date", "order_book_id"]).sum())
    if duplicate_key:
        issues.append(HXZQualityIssue("financial_factor_daily_pit", "error", "primary_key_unique", "duplicate trade_date/order_book_id rows", duplicate_key))
    dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    if dates.isna().any():
        issues.append(HXZQualityIssue("financial_factor_daily_pit", "error", "trade_date_format", "unparseable trade_date", int(dates.isna().sum())))
    for field in FACTOR_FIELDS:
        null_rate = float(frame[field].isna().mean())
        if null_rate > 0.2:
            issues.append(HXZQualityIssue("financial_factor_daily_pit", "warning", f"{field}_coverage", f"{field} null rate above 20%", int(frame[field].isna().sum())))
    for symbol, group in frame.groupby("order_book_id"):
        ordered = pd.to_datetime(group["trade_date"], errors="coerce").is_monotonic_increasing
        if not ordered:
            issues.append(HXZQualityIssue("financial_factor_daily_pit", "error", "date_order", f"dates not ordered for {symbol}", len(group)))
    return issues


def check_risk_free_rate(frame: pd.DataFrame) -> list[HXZQualityIssue]:
    issues: list[HXZQualityIssue] = []
    required = ["trade_date"] + RISK_FREE_FIELDS
    issues.extend(_required_columns("risk_free_rate", frame, required))
    if issues:
        return issues
    duplicate_key = int(frame.duplicated(["trade_date"]).sum())
    if duplicate_key:
        issues.append(HXZQualityIssue("risk_free_rate", "error", "primary_key_unique", "duplicate trade_date rows", duplicate_key))
    for field in RISK_FREE_FIELDS:
        values = pd.to_numeric(frame[field], errors="coerce")
        bad = values.isna() | (values < -0.05) | (values > 0.25)
        if bad.any():
            issues.append(HXZQualityIssue("risk_free_rate", "error", f"{field}_reasonable_range", f"{field} outside decimal annual-rate range", int(bad.sum())))
    return issues


def _required_columns(dataset: str, frame: pd.DataFrame, required: list[str]) -> list[HXZQualityIssue]:
    missing = [field for field in required if field not in frame.columns]
    if missing:
        return [HXZQualityIssue(dataset, "error", "required_columns", f"missing columns: {', '.join(missing)}", len(missing))]
    return []
