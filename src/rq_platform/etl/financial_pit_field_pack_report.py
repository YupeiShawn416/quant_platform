from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.financial_pit_field_pack_quality import (
    FinancialPitFieldPackIssue,
    check_financial_pit_field_pack,
    reconcile_with_financial_pit_quarterly,
    summarize_financial_pit_field_pack,
)


def write_financial_pit_field_pack_quality_report(
    frame: pd.DataFrame,
    output_dir: str | Path = "reports/generated",
    dataset_name: str = "financial_pit_field_pack",
    title: str = "Financial PIT Field Pack",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    issues = check_financial_pit_field_pack(frame)
    summary = summarize_financial_pit_field_pack(frame)
    payload = {
        "status": "failed" if any(issue.severity == "error" for issue in issues) else "success",
        "issue_count": len(issues),
        "issues": [issue.to_dict() for issue in issues],
        "summary": summary,
    }
    json_path = output / f"{dataset_name}_quality.json"
    md_path = output / f"{dataset_name}_quality.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_quality_markdown(payload, title), encoding="utf-8")
    return {"quality_json": json_path, "quality_md": md_path}


def write_financial_pit_field_pack_coverage_report(
    frame: pd.DataFrame,
    output_dir: str | Path = "reports/generated",
    dataset_name: str = "financial_pit_field_pack",
    title: str = "Financial PIT Field Pack",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    summary = summarize_financial_pit_field_pack(frame)
    json_path = output / f"{dataset_name}_coverage.json"
    md_path = output / f"{dataset_name}_coverage.md"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_coverage_markdown(summary, title), encoding="utf-8")
    return {"coverage_json": json_path, "coverage_md": md_path}


def write_financial_pit_field_pack_reconcile_report(
    frame: pd.DataFrame,
    output_dir: str | Path = "reports/generated",
    dataset_name: str = "financial_pit_field_pack",
    title: str = "Financial PIT Field Pack",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result = reconcile_with_financial_pit_quarterly(frame)
    json_path = output / f"{dataset_name}_reconcile.json"
    md_path = output / f"{dataset_name}_reconcile.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_reconcile_markdown(result, title), encoding="utf-8")
    return {"reconcile_json": json_path, "reconcile_md": md_path}


def render_quality_markdown(payload: dict[str, Any], title: str = "Financial PIT Field Pack") -> str:
    lines = [
        f"# {title} Quality",
        "",
        f"Status: `{payload['status']}`",
        f"Issue count: `{payload['issue_count']}`",
        "",
        "## Issues",
        "",
    ]
    issues = payload["issues"]
    if issues:
        lines.extend(_markdown_table(pd.DataFrame(issues), ["severity", "check", "message", "count"]))
    else:
        lines.append("No issues.")
    lines.extend(["", "## Field Coverage", ""])
    lines.extend(_markdown_table(pd.DataFrame(payload["summary"].get("field_stats", [])), ["canonical_field", "row_count", "non_null_count", "non_null_ratio", "latest_non_null_date", "ready"]))
    return "\n".join(lines) + "\n"


def render_coverage_markdown(summary: dict[str, Any], title: str = "Financial PIT Field Pack") -> str:
    lines = [
        f"# {title} Coverage",
        "",
        f"Rows: `{summary.get('row_count', 0)}`",
        f"Symbols: `{summary.get('symbol_count', 0)}`",
        f"Report periods: `{summary.get('report_period_count', 0)}`",
        f"Info date range: `{summary.get('date_range', '')}`",
        "",
        "## Year Counts",
        "",
    ]
    year_counts = summary.get("year_counts", {})
    if year_counts:
        lines.extend(_markdown_table(pd.DataFrame([{"year": year, "rows": count} for year, count in year_counts.items()]), ["year", "rows"]))
    else:
        lines.append("No rows.")
    lines.extend(["", "## Field Coverage", ""])
    lines.extend(_markdown_table(pd.DataFrame(summary.get("field_stats", [])), ["canonical_field", "non_null_count", "non_null_ratio", "first_info_date", "latest_info_date"]))
    return "\n".join(lines) + "\n"


def render_reconcile_markdown(result: dict[str, Any], title: str = "Financial PIT Field Pack") -> str:
    lines = [
        f"# {title} Reconcile",
        "",
        f"Status: `{result.get('status')}`",
        f"Overlap fields: `{', '.join(result.get('overlap_fields', []))}`",
        f"Newly available fields: `{', '.join(result.get('newly_available_fields', []))}`",
        "",
        "## Overlap Samples",
        "",
    ]
    lines.extend(_markdown_table(pd.DataFrame(result.get("samples", [])), ["field", "matched_rows", "max_abs_diff", "mean_abs_diff"]))
    return "\n".join(lines) + "\n"


def _markdown_table(df: pd.DataFrame, columns: list[str]) -> list[str]:
    if df.empty:
        return ["No rows."]
    view = df.reindex(columns=columns).fillna("")
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in view.to_dict(orient="records"):
        lines.append("| " + " | ".join(str(row[column]).replace("|", "\\|") for column in columns) + " |")
    return lines
