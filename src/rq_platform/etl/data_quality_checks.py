from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings

CORE_STATUS_DATASETS = {"prices", "index_prices", "tradability", "valuation", "industry", "index_members"}
PRICE_DATASETS = ["prices_1d_pre", "prices_1d_none", "index_prices_1d"]


@dataclass
class QualityIssue:
    dataset: str
    severity: str
    message: str
    path: str | None = None

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
        }


def run_data_quality_checks(
    data_root: str | Path | None = None,
    expected_end_date: str | None = None,
) -> list[QualityIssue]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    issues: list[QualityIssue] = []
    for path in sorted(root.glob("*/*.parquet")):
        dataset = path.parent.name
        try:
            frame = pd.read_parquet(path)
        except Exception as exc:
            issues.append(QualityIssue(dataset, "error", f"cannot read parquet: {type(exc).__name__}: {exc}", str(path)))
            continue
        issues.extend(check_duplicate_keys(dataset, frame, path))
        issues.extend(check_ohlc(dataset, frame, path))
        issues.extend(check_non_negative(dataset, frame, path))
    issues.extend(check_cross_dataset_coverage(root))
    target_end = expected_end_date or _latest_trading_date(root)
    if target_end:
        issues.extend(check_expected_end_date_coverage(root, target_end))
    issues.extend(check_daily_update_status_zero_rows(root))
    return issues


def check_duplicate_keys(dataset: str, frame: pd.DataFrame, path: Path | None = None) -> list[QualityIssue]:
    keys = _key_columns(frame)
    if not keys:
        return []
    duplicate_count = int(frame.duplicated(keys).sum())
    if duplicate_count:
        return [QualityIssue(dataset, "error", f"duplicate keys {keys}: {duplicate_count}", str(path) if path else None)]
    return []


def check_ohlc(dataset: str, frame: pd.DataFrame, path: Path | None = None) -> list[QualityIssue]:
    required = {"open", "high", "low", "close"}
    if not required.issubset(frame.columns) or frame.empty:
        return []
    numeric = frame[list(required)].apply(pd.to_numeric, errors="coerce")
    bad = (
        (numeric["high"] < numeric["low"])
        | (numeric["high"] < numeric["open"])
        | (numeric["high"] < numeric["close"])
        | (numeric["low"] > numeric["open"])
        | (numeric["low"] > numeric["close"])
    )
    if bool(bad.any()):
        return [QualityIssue(dataset, "error", f"OHLC inconsistent rows: {int(bad.sum())}", str(path) if path else None)]
    return []


def check_non_negative(dataset: str, frame: pd.DataFrame, path: Path | None = None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    for column in ["volume", "total_turnover"]:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            bad = values < 0
            if bool(bad.any()):
                issues.append(QualityIssue(dataset, "error", f"{column} negative rows: {int(bad.sum())}", str(path) if path else None))
    return issues


def check_cross_dataset_coverage(root: Path) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    pre_years = _years(root / "prices_1d_pre")
    none_years = _years(root / "prices_1d_none")
    if pre_years != none_years:
        issues.append(QualityIssue("prices", "warning", f"pre/none year coverage mismatch: pre={sorted(pre_years)} none={sorted(none_years)}"))
    max_dates = {
        dataset: _dataset_max_date(root / dataset)
        for dataset in ["prices_1d_pre", "prices_1d_none", "index_prices_1d", "tradability_1d", "valuation_1d"]
    }
    non_empty = {key: value for key, value in max_dates.items() if value}
    if len(set(non_empty.values())) > 1:
        issues.append(QualityIssue("coverage", "warning", f"core dataset max_date mismatch: {non_empty}"))
    return issues


def check_expected_end_date_coverage(root: Path, expected_end_date: str) -> list[QualityIssue]:
    if not _is_trading_day(root, expected_end_date):
        return []
    issues: list[QualityIssue] = []
    for dataset in PRICE_DATASETS:
        max_date = _dataset_max_date(root / dataset)
        if max_date is None or max_date < expected_end_date:
            issues.append(
                QualityIssue(
                    dataset,
                    "error",
                    f"max_date {max_date or 'missing'} is earlier than expected trading date {expected_end_date}",
                    str(root / dataset),
                )
            )
    return issues


def check_daily_update_status_zero_rows(root: Path) -> list[QualityIssue]:
    status_path = root / "update_logs" / "daily_update_status.csv"
    if not status_path.exists():
        return []
    try:
        frame = pd.read_csv(status_path)
    except Exception as exc:
        return [QualityIssue("daily_update_status", "warning", f"cannot read status log: {type(exc).__name__}", str(status_path))]
    if frame.empty or not {"dataset", "status", "row_count"}.issubset(frame.columns):
        return []
    rows = frame[
        frame["dataset"].astype(str).isin(CORE_STATUS_DATASETS)
        & (frame["status"].astype(str) == "success")
        & (pd.to_numeric(frame["row_count"], errors="coerce").fillna(0).astype(int) == 0)
    ]
    issues: list[QualityIssue] = []
    for row_index, row in rows.iterrows():
        start_date = str(row.get("start_date") or "")
        end_date = str(row.get("end_date") or "")
        dataset = str(row.get("dataset"))
        if _has_later_successful_repair(frame, row_index, dataset, start_date, end_date):
            continue
        if _has_trading_days(root, start_date, end_date):
            issues.append(
                QualityIssue(
                    dataset,
                    "error",
                    f"daily update status success with row_count=0 for trading range {start_date} to {end_date}",
                    str(status_path),
                )
            )
    return issues


def _has_later_successful_repair(
    frame: pd.DataFrame,
    row_index: int,
    dataset: str,
    start_date: str,
    end_date: str,
) -> bool:
    if not start_date or not end_date:
        return False
    later = frame.loc[row_index + 1 :].copy()
    if later.empty:
        return False
    later = later[
        (later["dataset"].astype(str) == dataset)
        & (later["status"].astype(str) == "success")
        & (pd.to_numeric(later["row_count"], errors="coerce").fillna(0).astype(int) > 0)
    ]
    if later.empty:
        return False
    later_start = later["start_date"].astype(str)
    later_end = later["end_date"].astype(str)
    return bool(((later_start <= start_date) & (later_end >= end_date)).any())


def write_quality_report(
    issues: list[QualityIssue],
    output_dir: str | Path = "reports/generated",
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "data_quality_2016_present.json"
    md_path = output / "data_quality_2016_present.md"
    data = [issue.to_dict() for issue in issues]
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_quality_markdown(issues), encoding="utf-8")
    return md_path, json_path


def render_quality_markdown(issues: list[QualityIssue]) -> str:
    lines = ["# Data Quality 2016 Present", ""]
    if not issues:
        lines.append("No issues found.")
        return "\n".join(lines) + "\n"
    lines.extend(["| dataset | severity | message | path |", "| --- | --- | --- | --- |"])
    for issue in issues:
        lines.append(f"| {issue.dataset} | {issue.severity} | {issue.message} | {issue.path or ''} |")
    return "\n".join(lines) + "\n"


def _key_columns(frame: pd.DataFrame) -> list[str]:
    for keys in [
        ["trade_date", "order_book_id", "adjust_type"],
        ["trade_date", "order_book_id"],
        ["trade_date", "index_id", "order_book_id"],
    ]:
        if set(keys).issubset(frame.columns):
            return keys
    return []


def _years(path: Path) -> set[int]:
    years = set()
    for file_path in path.glob("year=*.parquet"):
        try:
            years.add(int(file_path.stem.split("=", 1)[1]))
        except Exception:
            continue
    return years


def _dataset_max_date(path: Path) -> str | None:
    values = [_file_max_date(file_path) for file_path in sorted(path.glob("*.parquet"))]
    values = [value for value in values if value]
    return max(values) if values else None


def _file_max_date(path: Path) -> str | None:
    try:
        frame = pd.read_parquet(path, columns=["trade_date"])
    except Exception:
        return None
    if frame.empty:
        return None
    dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    if dates.empty:
        return None
    return dates.max().strftime("%Y-%m-%d")


def _latest_trading_date(root: Path) -> str | None:
    calendar_path = root / "trading_calendar" / "trading_calendar.parquet"
    if not calendar_path.exists():
        return None
    try:
        frame = pd.read_parquet(calendar_path)
    except Exception:
        return None
    frame = _calendar_trade_dates(frame)
    if frame.empty:
        return None
    return frame["trade_date"].max()


def _is_trading_day(root: Path, trade_date: str) -> bool:
    return bool(trade_date and trade_date in _trading_dates(root, trade_date, trade_date))


def _has_trading_days(root: Path, start_date: str, end_date: str) -> bool:
    if not start_date or not end_date:
        return False
    return bool(_trading_dates(root, start_date, end_date))


def _trading_dates(root: Path, start_date: str, end_date: str) -> list[str]:
    calendar_path = root / "trading_calendar" / "trading_calendar.parquet"
    if not calendar_path.exists():
        return []
    try:
        frame = pd.read_parquet(calendar_path)
    except Exception:
        return []
    frame = _calendar_trade_dates(frame)
    frame = frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)]
    return frame["trade_date"].tolist()


def _calendar_trade_dates(frame: pd.DataFrame) -> pd.DataFrame:
    if "trade_date" not in frame.columns:
        return pd.DataFrame(columns=["trade_date"])
    output = frame.copy()
    output["trade_date"] = pd.to_datetime(output["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    output = output.dropna(subset=["trade_date"])
    if "is_open" in output.columns:
        output = output[output["is_open"].astype(bool)]
    return output[["trade_date"]].drop_duplicates().sort_values("trade_date").reset_index(drop=True)
