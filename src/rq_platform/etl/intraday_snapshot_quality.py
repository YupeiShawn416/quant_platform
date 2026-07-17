from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from rq_platform.etl.intraday_snapshot_plan import CORE_SNAPSHOT_TIMES, DEFAULT_SNAPSHOT_TIMES, STATUS_PATH
from rq_platform.settings import settings


@dataclass
class IntradaySnapshotIssue:
    dataset: str
    severity: str
    message: str
    path: str = ""

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "severity": self.severity,
            "message": self.message,
            "path": self.path,
        }


def check_intraday_snapshot_quality(
    data_root: str | Path | None = None,
    min_symbols_per_snapshot: int = 100,
) -> list[IntradaySnapshotIssue]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    dataset_root = root / "intraday_snapshots"
    issues: list[IntradaySnapshotIssue] = []
    if not dataset_root.exists():
        return [IntradaySnapshotIssue("intraday_snapshots", "warning", "dataset not found", str(dataset_root))]
    for path in sorted(dataset_root.glob("year=*/month=*.parquet")):
        issues.extend(_check_file(path, min_symbols_per_snapshot=min_symbols_per_snapshot))
    issues.extend(check_intraday_snapshot_status_log(root / "update_logs" / "intraday_snapshot_update_status.csv"))
    return issues


def check_intraday_snapshot_status_log(status_path: str | Path | None = None) -> list[IntradaySnapshotIssue]:
    path = Path(status_path) if status_path is not None else STATUS_PATH
    if not path.exists():
        return []
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return [IntradaySnapshotIssue("intraday_snapshots", "warning", f"cannot read status log: {type(exc).__name__}", str(path))]
    issues: list[IntradaySnapshotIssue] = []
    if frame.empty:
        return issues
    success_zero = frame[(frame.get("status") == "success") & (pd.to_numeric(frame.get("row_count"), errors="coerce").fillna(0) <= 0)]
    for _, row in success_zero.iterrows():
        issues.append(
            IntradaySnapshotIssue(
                "intraday_snapshots",
                "error",
                f"status success with row_count=0 for {row.get('start_date')} to {row.get('end_date')} {row.get('snapshot_time')}",
                str(path),
            )
        )
    return issues


def load_intraday_snapshot_files(data_root: str | Path | None = None) -> list[Path]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    return sorted((root / "intraday_snapshots").glob("year=*/month=*.parquet"))


def summarize_intraday_snapshot_coverage(data_root: str | Path | None = None) -> pd.DataFrame:
    rows: list[dict] = []
    for path in load_intraday_snapshot_files(data_root):
        try:
            frame = pd.read_parquet(path)
            if frame.empty:
                rows.append(_coverage_row(path, frame, None))
                continue
            for snapshot_time, group in frame.groupby("snapshot_time"):
                rows.append(_coverage_row(path, group, str(snapshot_time)))
        except Exception as exc:
            rows.append({"path": str(path), "error": f"{type(exc).__name__}: {exc}"})
    return pd.DataFrame(rows)


def _check_file(path: Path, *, min_symbols_per_snapshot: int) -> list[IntradaySnapshotIssue]:
    issues: list[IntradaySnapshotIssue] = []
    try:
        frame = pd.read_parquet(path)
    except Exception as exc:
        return [IntradaySnapshotIssue("intraday_snapshots", "error", f"cannot read parquet: {type(exc).__name__}", str(path))]
    if frame.empty:
        return [IntradaySnapshotIssue("intraday_snapshots", "warning", "empty parquet file", str(path))]

    keys = ["trade_date", "snapshot_time", "order_book_id"]
    if set(keys).issubset(frame.columns):
        duplicate_count = int(frame.duplicated(keys).sum())
        if duplicate_count:
            issues.append(IntradaySnapshotIssue("intraday_snapshots", "error", f"duplicate keys: {duplicate_count}", str(path)))
    else:
        issues.append(IntradaySnapshotIssue("intraday_snapshots", "error", "missing duplicate key columns", str(path)))

    if "snapshot_time" in frame.columns:
        actual_times = set(frame["snapshot_time"].dropna().astype(str))
        outside = sorted(actual_times - set(DEFAULT_SNAPSHOT_TIMES))
        if outside:
            issues.append(IntradaySnapshotIssue("intraday_snapshots", "error", f"outside snapshot_time values: {','.join(outside)}", str(path)))
        missing_core = sorted(set(CORE_SNAPSHOT_TIMES) - actual_times)
        if missing_core:
            issues.append(IntradaySnapshotIssue("intraday_snapshots", "error", f"missing core snapshot_time values: {','.join(missing_core)}", str(path)))

    issues.extend(_non_positive_issues(frame, path))
    issues.extend(_low_coverage_issues(frame, path, min_symbols_per_snapshot))
    return issues


def _non_positive_issues(frame: pd.DataFrame, path: Path) -> list[IntradaySnapshotIssue]:
    issues: list[IntradaySnapshotIssue] = []
    for column, op, message in [
        ("close", "le", "close <= 0"),
        ("volume", "lt", "volume < 0"),
        ("total_turnover", "lt", "total_turnover < 0"),
    ]:
        if column not in frame.columns:
            if column in {"volume", "total_turnover"}:
                issues.append(IntradaySnapshotIssue("intraday_snapshots", "warning", f"{column} field is missing", str(path)))
            else:
                issues.append(IntradaySnapshotIssue("intraday_snapshots", "error", f"{column} field is missing", str(path)))
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        bad = values <= 0 if op == "le" else values < 0
        count = int(bad.fillna(False).sum())
        if count:
            severity = "error" if column == "close" else "warning"
            issues.append(IntradaySnapshotIssue("intraday_snapshots", severity, f"{message}: {count}", str(path)))
    return issues


def _low_coverage_issues(frame: pd.DataFrame, path: Path, min_symbols_per_snapshot: int) -> list[IntradaySnapshotIssue]:
    if not {"trade_date", "snapshot_time", "order_book_id"}.issubset(frame.columns):
        return []
    counts = frame.groupby(["trade_date", "snapshot_time"])["order_book_id"].nunique()
    low = counts[counts < min_symbols_per_snapshot]
    return [
        IntradaySnapshotIssue(
            "intraday_snapshots",
            "warning",
            f"low symbol coverage {int(value)} for {date_value} {time_value}",
            str(path),
        )
        for (date_value, time_value), value in low.items()
    ]


def _coverage_row(path: Path, frame: pd.DataFrame, snapshot_time: str | None) -> dict:
    dates = pd.to_datetime(frame.get("trade_date"), errors="coerce").dropna() if "trade_date" in frame.columns else pd.Series(dtype="datetime64[ns]")
    return {
        "path": str(path),
        "year": _parse_partition(path, "year"),
        "month": _parse_month(path),
        "snapshot_time": snapshot_time or "",
        "rows": int(len(frame)),
        "symbols": int(frame["order_book_id"].nunique()) if "order_book_id" in frame.columns and not frame.empty else 0,
        "min_date": dates.min().strftime("%Y-%m-%d") if not dates.empty else "",
        "max_date": dates.max().strftime("%Y-%m-%d") if not dates.empty else "",
        "duplicate_keys": int(frame.duplicated(["trade_date", "snapshot_time", "order_book_id"]).sum()) if {"trade_date", "snapshot_time", "order_book_id"}.issubset(frame.columns) else None,
        "error": "",
    }


def _parse_partition(path: Path, prefix: str) -> int | None:
    for part in path.parts:
        if part.startswith(f"{prefix}="):
            try:
                return int(part.split("=", 1)[1])
            except ValueError:
                return None
    return None


def _parse_month(path: Path) -> int | None:
    try:
        return int(path.stem.split("=", 1)[1])
    except Exception:
        return None
