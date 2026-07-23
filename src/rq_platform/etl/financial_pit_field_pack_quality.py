from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.financial_pit_field_pack_core import DATASET_NAME, KEY_COLUMNS
from rq_platform.settings import settings


@dataclass(frozen=True)
class FinancialPitFieldPackIssue:
    severity: str
    check: str
    message: str
    count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def load_financial_pit_field_pack(data_root: str | Path | None = None, dataset_name: str = DATASET_NAME) -> pd.DataFrame:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    files = sorted((root / dataset_name).rglob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)


def check_financial_pit_field_pack(frame: pd.DataFrame) -> list[FinancialPitFieldPackIssue]:
    issues: list[FinancialPitFieldPackIssue] = []
    required = ["order_book_id", "report_period", "info_date"]
    missing = [field for field in required if field not in frame.columns]
    if missing:
        return [FinancialPitFieldPackIssue("error", "required_columns", f"missing columns: {', '.join(missing)}", len(missing))]
    if frame.empty:
        issues.append(FinancialPitFieldPackIssue("error", "row_count", "financial PIT field pack is empty", 0))
        return issues

    duplicate_keys = int(frame.duplicated(_key_columns(frame)).sum())
    if duplicate_keys:
        issues.append(FinancialPitFieldPackIssue("error", "duplicate_key", "duplicate PIT keys", duplicate_keys))

    info_dates = pd.to_datetime(frame["info_date"], errors="coerce")
    bad_info_dates = int(info_dates.isna().sum())
    if bad_info_dates:
        issues.append(FinancialPitFieldPackIssue("error", "info_date_parse", "unparseable info_date", bad_info_dates))

    periods = frame["report_period"].astype(str)
    period_ok = periods.str.match(r"^\d{4}q[1-4]$").fillna(False)
    bad_periods = int((~period_ok).sum())
    if bad_periods:
        issues.append(FinancialPitFieldPackIssue("error", "report_period_parse", "unparseable report_period", bad_periods))

    if not any(column in frame.columns for column in ["info_date", "announcement_date", "publish_date"]):
        issues.append(FinancialPitFieldPackIssue("error", "pit_date_missing", "no PIT announcement date column exists", len(frame)))

    for field in financial_value_columns(frame):
        non_null = int(pd.to_numeric(frame[field], errors="coerce").notna().sum())
        if non_null == 0:
            issues.append(FinancialPitFieldPackIssue("error", f"{field}_all_empty", f"{field} has no numeric coverage", len(frame)))

    if "info_date" in frame.columns and "report_period" in frame.columns:
        report_end = frame["report_period"].map(_quarter_end)
        future_risk = (pd.to_datetime(frame["info_date"], errors="coerce") < pd.to_datetime(report_end, errors="coerce")).fillna(False)
        if future_risk.any():
            issues.append(FinancialPitFieldPackIssue("error", "pit_future_risk", "info_date is earlier than report period end", int(future_risk.sum())))
    return issues


def summarize_financial_pit_field_pack(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"row_count": 0, "symbol_count": 0, "report_period_count": 0, "date_range": "", "field_stats": []}
    info_dates = pd.to_datetime(frame["info_date"], errors="coerce")
    stats = []
    for field in financial_value_columns(frame):
        values = pd.to_numeric(frame[field], errors="coerce")
        non_null = values.notna()
        latest_non_null = ""
        if non_null.any():
            latest_non_null = info_dates[non_null].max().date().isoformat()
        stats.append(
            {
                "canonical_field": field,
                "row_count": int(len(frame)),
                "non_null_count": int(non_null.sum()),
                "non_null_ratio": float(non_null.mean()),
                "first_info_date": info_dates.min().date().isoformat() if info_dates.notna().any() else "",
                "latest_info_date": info_dates.max().date().isoformat() if info_dates.notna().any() else "",
                "latest_non_null_date": latest_non_null,
                "ready": bool(non_null.any()),
            }
        )
    year_counts = {}
    if info_dates.notna().any():
        year_counts = {str(int(year)): int(count) for year, count in info_dates.dt.year.value_counts().sort_index().items()}
    return {
        "row_count": int(len(frame)),
        "symbol_count": int(frame["order_book_id"].nunique()) if "order_book_id" in frame.columns else 0,
        "report_period_count": int(frame["report_period"].nunique()) if "report_period" in frame.columns else 0,
        "date_range": _date_range(info_dates),
        "year_counts": year_counts,
        "field_stats": stats,
    }


def financial_value_columns(frame: pd.DataFrame) -> list[str]:
    excluded = {
        "order_book_id",
        "report_period",
        "quarter",
        "info_date",
        "announcement_date",
        "publish_date",
        "rice_create_tm",
        "if_adjusted",
        "statement_type",
        "field_mapping_json",
        "source",
        "fetched_at",
    }
    return [column for column in frame.columns if column not in excluded]


def reconcile_with_financial_pit_quarterly(
    field_pack: pd.DataFrame,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    files = sorted((root / "financial_pit_quarterly").rglob("*.parquet"))
    if not files:
        return {"status": "missing_old_dataset", "overlap_fields": [], "samples": []}
    old = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    old = old.rename(columns={"quarter": "report_period"})
    overlaps = sorted(set(financial_value_columns(field_pack)) & set(financial_value_columns(old)))
    samples = []
    if overlaps:
        merged = field_pack.merge(old, on=["order_book_id", "report_period", "info_date"], how="inner", suffixes=("_new", "_old"))
        for field in overlaps:
            new_col = f"{field}_new"
            old_col = f"{field}_old"
            if new_col in merged.columns and old_col in merged.columns:
                diff = (pd.to_numeric(merged[new_col], errors="coerce") - pd.to_numeric(merged[old_col], errors="coerce")).abs()
                samples.append(
                    {
                        "field": field,
                        "matched_rows": int(len(merged)),
                        "max_abs_diff": float(diff.max()) if diff.notna().any() else None,
                        "mean_abs_diff": float(diff.mean()) if diff.notna().any() else None,
                    }
                )
    return {
        "status": "success",
        "overlap_fields": overlaps,
        "newly_available_fields": sorted(set(financial_value_columns(field_pack)) - set(financial_value_columns(old))),
        "samples": samples,
    }


def _key_columns(frame: pd.DataFrame) -> list[str]:
    keys = KEY_COLUMNS.copy()
    if "statement_type" in frame.columns and frame["statement_type"].notna().any():
        keys.append("statement_type")
    return keys


def _quarter_end(period: str) -> str:
    text = str(period).lower()
    year = text[:4]
    quarter = text[-1:]
    return {
        "1": f"{year}-03-31",
        "2": f"{year}-06-30",
        "3": f"{year}-09-30",
        "4": f"{year}-12-31",
    }.get(quarter, "")


def _date_range(dates: pd.Series) -> str:
    if dates.notna().any():
        return f"{dates.min().date().isoformat()} to {dates.max().date().isoformat()}"
    return ""
