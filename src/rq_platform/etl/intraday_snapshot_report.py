from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.intraday_snapshot_quality import (
    IntradaySnapshotIssue,
    summarize_intraday_snapshot_coverage,
)


def write_intraday_snapshot_quality_report(
    *,
    quality_issues: list[IntradaySnapshotIssue],
    data_root: str | Path | None = None,
    output_dir: str | Path = "reports/generated",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    coverage = summarize_intraday_snapshot_coverage(data_root)
    data = build_intraday_snapshot_report(quality_issues=quality_issues, coverage=coverage)
    json_path = output / "intraday_snapshot_quality.json"
    md_path = output / "intraday_snapshot_quality.md"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_intraday_snapshot_report_markdown(data), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(md_path), "status": data["status"]}


def write_intraday_snapshot_coverage_report(
    *,
    data_root: str | Path | None = None,
    output_dir: str | Path = "reports/generated",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    coverage = summarize_intraday_snapshot_coverage(data_root)
    data = {"coverage": coverage.fillna("").to_dict(orient="records")}
    json_path = output / "intraday_snapshot_coverage.json"
    md_path = output / "intraday_snapshot_coverage.md"
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_intraday_snapshot_coverage_markdown(coverage), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(md_path), "rows": int(len(coverage))}


def build_intraday_snapshot_report(
    *,
    quality_issues: list[IntradaySnapshotIssue],
    coverage: pd.DataFrame,
) -> dict[str, Any]:
    issue_dicts = [issue.to_dict() for issue in quality_issues]
    error_count = sum(1 for item in issue_dicts if item.get("severity") == "error")
    warning_count = sum(1 for item in issue_dicts if item.get("severity") == "warning")
    return {
        "status": "failed" if error_count else "success",
        "quality_issues_count": len(issue_dicts),
        "quality_error_count": error_count,
        "quality_warning_count": warning_count,
        "issues": issue_dicts,
        "coverage": coverage.fillna("").to_dict(orient="records"),
    }


def render_intraday_snapshot_report_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Intraday Snapshot Quality",
        "",
        f"status: {data['status']}",
        f"quality_issues_count: {data['quality_issues_count']}",
        f"quality_error_count: {data['quality_error_count']}",
        f"quality_warning_count: {data['quality_warning_count']}",
        "",
        "## Issues",
        "",
    ]
    if not data["issues"]:
        lines.append("No issues.")
    else:
        lines.append("| severity | dataset | message | path |")
        lines.append("| --- | --- | --- | --- |")
        for issue in data["issues"]:
            lines.append(f"| {issue['severity']} | {issue['dataset']} | {issue['message']} | {issue['path']} |")
    lines.extend(["", "## Coverage", ""])
    lines.append(render_intraday_snapshot_coverage_markdown(pd.DataFrame(data["coverage"])).rstrip())
    return "\n".join(lines) + "\n"


def render_intraday_snapshot_coverage_markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No intraday snapshot coverage found.\n"
    columns = ["year", "month", "snapshot_time", "rows", "symbols", "min_date", "max_date", "duplicate_keys", "error"]
    available = [column for column in columns if column in frame.columns]
    lines = ["| " + " | ".join(available) + " |", "| " + " | ".join(["---"] * len(available)) + " |"]
    for _, row in frame[available].fillna("").iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in available) + " |")
    return "\n".join(lines) + "\n"
