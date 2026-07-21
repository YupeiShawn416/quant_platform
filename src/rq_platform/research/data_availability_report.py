from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


RAW_AVAILABILITY_COLUMNS = [
    "priority",
    "data_pack",
    "canonical_field",
    "chinese_name",
    "field_type",
    "required_frequency",
    "recommended_storage_frequency",
    "local_status",
    "local_dataset",
    "local_field",
    "local_row_count",
    "local_symbol_count",
    "local_non_null_ratio",
    "local_latest_non_null_date",
    "local_date_range",
    "rqdata_probe_enabled",
    "rqdata_status",
    "rqdata_candidate_function",
    "rqdata_candidate_field",
    "rqdata_sample_rows",
    "rqdata_error",
    "recommended_dataset_name",
    "backfill_priority",
    "notes",
]

DERIVED_DEPENDENCY_COLUMNS = [
    "priority",
    "data_pack",
    "derived_field",
    "chinese_name",
    "required_frequency",
    "formula",
    "required_raw_fields",
    "current_raw_field_status",
    "missing_raw_fields",
    "recommended_materialization",
    "notes",
]

BACKFILL_PLAN_COLUMNS = [
    "priority",
    "data_pack",
    "missing_raw_fields",
    "partial_or_stale_fields",
    "derived_blocked_fields",
    "field_count",
    "recommended_action",
]


def build_backfill_plan(raw_availability: list[dict[str, Any]], derived_dependency: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_df = pd.DataFrame(raw_availability)
    derived_df = pd.DataFrame(derived_dependency)
    packs = sorted(set(raw_df.get("data_pack", [])) | set(derived_df.get("data_pack", [])))
    rows = []
    for pack in packs:
        raw_pack = raw_df[raw_df["data_pack"] == pack] if not raw_df.empty else pd.DataFrame()
        derived_pack = derived_df[derived_df["data_pack"] == pack] if not derived_df.empty else pd.DataFrame()
        missing = _join(raw_pack.loc[raw_pack["local_status"] == "missing", "canonical_field"]) if not raw_pack.empty else ""
        partial = _join(
            raw_pack.loc[
                raw_pack["local_status"].isin(["partial", "available_but_latest_not_usable"]),
                "canonical_field",
            ]
        ) if not raw_pack.empty else ""
        blocked = _join(
            derived_pack.loc[
                derived_pack["current_raw_field_status"].str.startswith("blocked", na=False),
                "derived_field",
            ]
        ) if not derived_pack.empty else ""
        priorities = [item for item in raw_pack.get("priority", pd.Series(dtype=str)).tolist() + derived_pack.get("priority", pd.Series(dtype=str)).tolist() if item]
        priority = min(priorities, default="P3")
        rows.append(
            {
                "priority": priority,
                "data_pack": pack,
                "missing_raw_fields": missing,
                "partial_or_stale_fields": partial,
                "derived_blocked_fields": blocked,
                "field_count": int(len(raw_pack) + len(derived_pack)),
                "recommended_action": _recommended_action(priority, missing, partial, blocked),
            }
        )
    return sorted(rows, key=lambda row: (row["priority"], row["data_pack"]))


def write_research_report_availability_outputs(
    result: dict[str, Any],
    output_dir: str | Path = "reports/generated",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    raw_df = pd.DataFrame(result["raw_availability"]).reindex(columns=RAW_AVAILABILITY_COLUMNS)
    derived_df = pd.DataFrame(result["derived_dependency"]).reindex(columns=DERIVED_DEPENDENCY_COLUMNS)
    plan = build_backfill_plan(result["raw_availability"], result["derived_dependency"])
    plan_df = pd.DataFrame(plan).reindex(columns=BACKFILL_PLAN_COLUMNS)

    raw_csv = output / "research_report_raw_data_availability.csv"
    raw_json = output / "research_report_raw_data_availability.json"
    raw_md = output / "research_report_raw_data_availability.md"
    derived_csv = output / "research_report_derived_field_dependency.csv"
    derived_json = output / "research_report_derived_field_dependency.json"
    derived_md = output / "research_report_derived_field_dependency.md"
    plan_json = output / "research_report_data_backfill_plan.json"
    plan_md = output / "research_report_data_backfill_plan.md"

    raw_df.to_csv(raw_csv, index=False)
    derived_df.to_csv(derived_csv, index=False)
    plan_df.to_csv(output / "research_report_data_backfill_plan.csv", index=False)
    raw_json.write_text(json.dumps(result["raw_availability"], ensure_ascii=False, indent=2), encoding="utf-8")
    derived_json.write_text(json.dumps(result["derived_dependency"], ensure_ascii=False, indent=2), encoding="utf-8")
    plan_json.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    raw_md.write_text(render_raw_availability_markdown(result, raw_df), encoding="utf-8")
    derived_md.write_text(render_derived_dependency_markdown(result, derived_df), encoding="utf-8")
    plan_md.write_text(render_backfill_plan_markdown(result, plan_df), encoding="utf-8")

    return {
        "raw_csv": raw_csv,
        "raw_json": raw_json,
        "raw_md": raw_md,
        "derived_csv": derived_csv,
        "derived_json": derived_json,
        "derived_md": derived_md,
        "plan_json": plan_json,
        "plan_md": plan_md,
    }


def render_raw_availability_markdown(result: dict[str, Any], raw_df: pd.DataFrame) -> str:
    counts = raw_df["local_status"].value_counts(dropna=False).to_dict() if not raw_df.empty else {}
    lines = [
        "# Research Report Raw Data Availability",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"Data root: `{result['data_root']}`",
        f"RQData probe enabled: `{result['rqdata_probe_enabled']}`",
        "",
        "## Local Status Counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## P0/P1 Missing Or Stale Fields", ""])
    subset = raw_df[raw_df["local_status"].isin(["missing", "partial", "available_but_latest_not_usable"])]
    lines.extend(_markdown_table(subset, ["priority", "data_pack", "canonical_field", "local_status", "rqdata_candidate_function", "rqdata_candidate_field"]))
    return "\n".join(lines) + "\n"


def render_derived_dependency_markdown(result: dict[str, Any], derived_df: pd.DataFrame) -> str:
    counts = derived_df["current_raw_field_status"].value_counts(dropna=False).to_dict() if not derived_df.empty else {}
    lines = [
        "# Research Report Derived Field Dependency",
        "",
        f"Generated at: `{result['generated_at']}`",
        "",
        "Derived fields are not probed against RQData directly. They are checked through their raw-field dependencies.",
        "",
        "## Dependency Status Counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Blocked Derived Fields", ""])
    subset = derived_df[derived_df["current_raw_field_status"].str.startswith("blocked", na=False)]
    lines.extend(_markdown_table(subset, ["priority", "data_pack", "derived_field", "current_raw_field_status", "missing_raw_fields"]))
    return "\n".join(lines) + "\n"


def render_backfill_plan_markdown(result: dict[str, Any], plan_df: pd.DataFrame) -> str:
    lines = [
        "# Research Report Data Backfill Plan",
        "",
        f"Generated at: `{result['generated_at']}`",
        "",
        "This plan is a priority matrix only. It is not a full backfill run.",
        "",
    ]
    lines.extend(_markdown_table(plan_df, BACKFILL_PLAN_COLUMNS))
    return "\n".join(lines) + "\n"


def _recommended_action(priority: str, missing: str, partial: str, blocked: str) -> str:
    if missing or partial:
        return f"{priority} raw backfill/probe required"
    if blocked:
        return f"{priority} derived layer waits for raw field completion"
    return "covered locally or derivable from existing lake"


def _join(values: Any) -> str:
    return ",".join(str(item) for item in values if str(item))


def _markdown_table(df: pd.DataFrame, columns: list[str]) -> list[str]:
    if df.empty:
        return ["No rows."]
    view = df.reindex(columns=columns).fillna("")
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in view.to_dict(orient="records"):
        lines.append("| " + " | ".join(_cell(row[column]) for column in columns) + " |")
    return lines


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|")
