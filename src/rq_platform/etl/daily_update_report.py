from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rq_platform.etl.daily_update_plan import DailyUpdatePlan, get_data_lake_latest_date


def write_daily_update_report(
    *,
    plan: DailyUpdatePlan,
    results: list[Any],
    quality_issues: list[Any],
    output_dir: str | Path = "reports/generated",
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    data = build_daily_update_report(plan=plan, results=results, quality_issues=quality_issues)
    json_path = output / "daily_update_report.json"
    md_path = output / "daily_update_report.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_daily_update_report_markdown(data), encoding="utf-8")
    data["json_path"] = str(json_path)
    data["markdown_path"] = str(md_path)
    return data


def build_daily_update_report(
    *,
    plan: DailyUpdatePlan,
    results: list[Any],
    quality_issues: list[Any],
) -> dict[str, Any]:
    result_dicts = [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in results]
    issue_dicts = [item.to_dict() if hasattr(item, "to_dict") else dict(item) for item in quality_issues]
    failed = [item for item in result_dicts if item.get("status") == "failed"]
    error_issues = [item for item in issue_dicts if item.get("severity") == "error"]
    return {
        "start_date": plan.start_date,
        "end_date": plan.end_date,
        "latest_date_before_update": plan.latest_date,
        "latest_date_after_update": get_data_lake_latest_date(),
        "no_op": plan.no_op,
        "results": result_dicts,
        "quality_issues_count": len(issue_dicts),
        "quality_error_count": len(error_issues),
        "quality_issues": issue_dicts,
        "failed_datasets": sorted({item.get("dataset") for item in failed if item.get("dataset")}),
        "status": "failed" if failed or error_issues else "success",
        "recommend_rsync": not failed and not error_issues and not plan.no_op,
    }


def render_daily_update_report_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Daily Data Update Report",
        "",
        f"status: {data['status']}",
        f"start_date: {data['start_date']}",
        f"end_date: {data['end_date']}",
        f"latest_date_before_update: {data.get('latest_date_before_update') or ''}",
        f"latest_date_after_update: {data.get('latest_date_after_update') or ''}",
        f"quality_issues_count: {data['quality_issues_count']}",
        f"recommend_rsync: {data['recommend_rsync']}",
        "",
        "## Dataset Results",
        "",
        "| dataset | year | status | rows | start | end | error |",
        "| --- | --- | --- | ---: | --- | --- | --- |",
    ]
    if not data["results"]:
        lines.append("|  |  | no-op | 0 |  |  |  |")
    for item in data["results"]:
        lines.append(
            f"| {item.get('dataset') or ''} | {item.get('year') or ''} | {item.get('status') or ''} | "
            f"{item.get('row_count') or 0} | {item.get('start_date') or ''} | {item.get('end_date') or ''} | "
            f"{item.get('error') or ''} |"
        )
    lines.extend(["", "## Quality Issues", ""])
    if not data["quality_issues"]:
        lines.append("No issues found.")
    else:
        lines.extend(["| dataset | severity | message |", "| --- | --- | --- |"])
        for issue in data["quality_issues"]:
            lines.append(f"| {issue.get('dataset') or ''} | {issue.get('severity') or ''} | {issue.get('message') or ''} |")
    return "\n".join(lines) + "\n"
