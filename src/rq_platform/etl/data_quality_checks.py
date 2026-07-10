from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


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


def run_data_quality_checks(data_root: str | Path | None = None) -> list[QualityIssue]:
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
    return issues


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
