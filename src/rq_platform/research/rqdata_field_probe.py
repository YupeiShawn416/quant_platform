from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.research.data_availability_probe import classify_probe_exception
from rq_platform.settings import settings


P0_DATA_PACK_ORDER = [
    "valuation_core",
    "financial_pit_core",
    "corporate_actions_dividend_share_capital",
    "index_universe_extended",
    "industry_taxonomy",
    "daily_market_core",
]

P0_PROBE_COLUMNS = [
    "priority",
    "data_pack",
    "canonical_field",
    "chinese_name",
    "field_type",
    "required_frequency",
    "local_status",
    "rqdata_probe_status",
    "rqdata_candidate_function",
    "rqdata_candidate_field",
    "rqdata_frequency",
    "sample_start",
    "sample_end",
    "sample_symbols",
    "sample_row_count",
    "sample_non_null_count",
    "sample_non_null_ratio",
    "permission_status",
    "error_type",
    "error_message_sanitized",
    "recommended_action_after_probe",
    "recommended_dataset_name",
    "notes",
]

AFTER_PROBE_PLAN_COLUMNS = [
    "data_pack",
    "priority",
    "raw_fields_available_from_rqdata",
    "raw_fields_permission_required",
    "raw_fields_external_required",
    "raw_fields_still_unknown",
    "derived_fields_unlocked",
    "recommended_storage_frequency",
    "recommended_backfill_scope",
    "estimated_storage_level",
    "permission_risk",
    "recommended_next_stage",
    "go_or_no_go",
    "notes",
]

PROBE_SYMBOLS = [
    "000001.XSHE",
    "000002.XSHE",
    "600000.XSHG",
    "600519.XSHG",
    "300750.XSHE",
    "688981.XSHG",
]
PROBE_DATES = ["2024-12-31", "2025-07-01", "2026-07-09"]
VALUATION_EXTRA_DATES = ["2026-07-10", "2026-07-13"]


@dataclass(frozen=True)
class ProbeConfig:
    stage33_raw_csv: Path = Path("reports/generated/research_report_raw_data_availability.csv")
    stage33_derived_csv: Path = Path("reports/generated/research_report_derived_field_dependency.csv")
    output_dir: Path = Path("reports/generated")
    enable_rqdata_probe: bool = False


class RQDataFieldProbe:
    def __init__(self) -> None:
        self._rqdatac: Any | None = None
        self._initialized = False
        self._init_error: Exception | None = None

    def init(self) -> Any:
        if self._init_error is not None:
            raise self._init_error
        if self._initialized and self._rqdatac is not None:
            return self._rqdatac
        import rqdatac  # type: ignore

        token = settings.rqdata_license or os.environ.get("RQDATAC_KEY")
        if not token:
            self._init_error = RuntimeError("RQData credential is not configured for this shell.")
            raise self._init_error
        try:
            rqdatac.init(username="license", password=token)
        except Exception as exc:
            self._init_error = exc
            raise
        self._rqdatac = rqdatac
        self._initialized = True
        return rqdatac

    def probe_row(self, row: dict[str, Any]) -> dict[str, Any]:
        base = _base_output_row(row)
        try:
            rqdatac = self.init()
            frame = self._fetch_sample(rqdatac, row)
            row_count = int(len(frame))
            field = str(row.get("rqdata_candidate_field") or row.get("canonical_field") or "")
            non_null_count = _count_non_null(frame, field)
            status = _status_from_sample(row_count, non_null_count)
            base.update(
                {
                    "rqdata_probe_status": status,
                    "sample_row_count": row_count,
                    "sample_non_null_count": non_null_count,
                    "sample_non_null_ratio": float(non_null_count / row_count) if row_count else 0.0,
                    "permission_status": "ok",
                    "recommended_action_after_probe": _recommended_action(status),
                }
            )
        except Exception as exc:
            status = classify_probe_exception(exc)
            if status == "quota_limited":
                status = "permission_required"
            if status != "permission_required":
                status = _function_status_or_failed(row, exc)
            base.update(
                {
                    "rqdata_probe_status": status,
                    "permission_status": "blocked" if status == "permission_required" else "unknown",
                    "error_type": type(exc).__name__,
                    "error_message_sanitized": sanitize_error_message(str(exc)),
                    "recommended_action_after_probe": _recommended_action(status),
                }
            )
        return base

    def _fetch_sample(self, rqdatac: Any, row: dict[str, Any]) -> pd.DataFrame:
        function_name = str(row.get("rqdata_candidate_function") or "")
        field = str(row.get("rqdata_candidate_field") or row.get("canonical_field") or "")
        canonical = str(row.get("canonical_field") or "")
        if function_name == "get_factor":
            return _ensure_frame(
                rqdatac.get_factor(
                    PROBE_SYMBOLS,
                    [field],
                    start_date=PROBE_DATES[0],
                    end_date=VALUATION_EXTRA_DATES[-1] if row.get("data_pack") == "valuation_core" else PROBE_DATES[-1],
                    expect_df=True,
                )
            )
        if function_name == "get_pit_financials_ex":
            return _ensure_frame(
                rqdatac.get_pit_financials_ex(
                    order_book_ids=PROBE_SYMBOLS,
                    fields=[field],
                    start_quarter="2024q4",
                    end_quarter="2025q4",
                    date="2026-07-09",
                    statements="all",
                    market="cn",
                )
            ).reset_index()
        if function_name == "index_components":
            index_id = canonical.replace("index_members_", "")
            if index_id == "tech_chinext_star":
                raise RuntimeError("external synthetic universe; no direct rqdatac index id configured")
            components = rqdatac.index_components(index_id, date=PROBE_DATES[-1])
            weights = rqdatac.index_weights(index_id, date=PROBE_DATES[-1])
            frame = pd.DataFrame({"component_order_book_id": list(components or [])})
            if weights is not None:
                weight_frame = pd.Series(weights, name="weight").reset_index()
                weight_frame = weight_frame.rename(columns={weight_frame.columns[0]: "component_order_book_id"})
                frame = frame.merge(weight_frame, on="component_order_book_id", how="left")
            return frame
        if function_name == "industry":
            source, level = _industry_source_and_level(canonical)
            return _ensure_frame(
                rqdatac.get_instrument_industry(
                    PROBE_SYMBOLS,
                    source=source,
                    level=level,
                    date=PROBE_DATES[-1],
                )
            )
        if function_name in {"corporate_action", "topic_or_external", "fundamental_events"}:
            raise AttributeError(f"{function_name} direct probe is not mapped to a verified rqdatac function")
        if not function_name or not hasattr(rqdatac, function_name):
            raise AttributeError(f"{function_name or '<empty>'} not found")
        raise NotImplementedError(f"{function_name} probe is not implemented")


def load_p0_probe_inputs(raw_csv: str | Path) -> list[dict[str, Any]]:
    raw = pd.read_csv(raw_csv).fillna("")
    mask = (
        (raw["priority"] == "P0")
        & (raw["field_type"].isin(["raw", "label", "event", "metadata"]))
        & (raw["local_status"].isin(["missing", "available_but_need_coverage_check", "available_but_latest_not_usable"]))
        & (raw["data_pack"].isin(P0_DATA_PACK_ORDER))
    )
    out = raw.loc[mask].copy()
    order_map = {pack: idx for idx, pack in enumerate(P0_DATA_PACK_ORDER)}
    out["_pack_order"] = out["data_pack"].map(order_map)
    out = out.sort_values(["_pack_order", "canonical_field"]).drop(columns=["_pack_order"])
    return out.to_dict(orient="records")


def run_p0_rqdata_probe(config: ProbeConfig) -> dict[str, Any]:
    fields = load_p0_probe_inputs(config.stage33_raw_csv)
    if not config.enable_rqdata_probe:
        rows = [_not_probed_row(row) for row in fields]
    else:
        probe = RQDataFieldProbe()
        rows = [probe.probe_row(row) for row in fields]
    derived_rows = pd.read_csv(config.stage33_derived_csv).fillna("").to_dict(orient="records")
    plan = build_after_probe_plan(rows, derived_rows)
    result = {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "rqdata_probe_enabled": config.enable_rqdata_probe,
        "p0_field_count": len(fields),
        "probe_rows": rows,
        "after_probe_plan": plan,
    }
    write_p0_probe_outputs(result, config.output_dir)
    return result


def build_after_probe_plan(probe_rows: list[dict[str, Any]], derived_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    probe_df = pd.DataFrame(probe_rows).reindex(columns=P0_PROBE_COLUMNS)
    derived_df = pd.DataFrame(derived_rows)
    packs = [pack for pack in P0_DATA_PACK_ORDER if pack in set(probe_df["data_pack"])]
    rows = []
    for pack in packs:
        pack_df = probe_df[probe_df["data_pack"] == pack]
        available = _join(pack_df.loc[pack_df["rqdata_probe_status"] == "available", "canonical_field"])
        permission = _join(pack_df.loc[pack_df["rqdata_probe_status"] == "permission_required", "canonical_field"])
        external = _join(pack_df.loc[pack_df["recommended_action_after_probe"] == "external_source_required", "canonical_field"])
        unknown = _join(
            pack_df.loc[
                pack_df["rqdata_probe_status"].isin(["available_but_empty_sample", "unavailable", "function_not_found", "probe_failed", "quota_limited"]),
                "canonical_field",
            ]
        )
        unlocked = _unlocked_derived_fields(pack, pack_df, derived_df)
        storage = _storage_level(pack)
        permission_risk = _permission_risk(pack_df)
        go = _go_or_no_go(pack_df)
        rows.append(
            {
                "data_pack": pack,
                "priority": "P0",
                "raw_fields_available_from_rqdata": available,
                "raw_fields_permission_required": permission,
                "raw_fields_external_required": external,
                "raw_fields_still_unknown": unknown,
                "derived_fields_unlocked": unlocked,
                "recommended_storage_frequency": _recommended_storage_frequency(pack),
                "recommended_backfill_scope": _recommended_scope(pack),
                "estimated_storage_level": storage,
                "permission_risk": permission_risk,
                "recommended_next_stage": _recommended_next_stage(pack, go),
                "go_or_no_go": go,
                "notes": _plan_notes(pack, pack_df),
            }
        )
    return rows


def write_p0_probe_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    probe_df = pd.DataFrame(result["probe_rows"]).reindex(columns=P0_PROBE_COLUMNS)
    plan_df = pd.DataFrame(result["after_probe_plan"]).reindex(columns=AFTER_PROBE_PLAN_COLUMNS)

    csv_path = output / "research_report_p0_rqdata_probe.csv"
    json_path = output / "research_report_p0_rqdata_probe.json"
    md_path = output / "research_report_p0_rqdata_probe.md"
    plan_json = output / "research_report_data_backfill_plan_after_probe.json"
    plan_md = output / "research_report_data_backfill_plan_after_probe.md"

    probe_df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(result["probe_rows"], ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_p0_probe_markdown(result, probe_df), encoding="utf-8")
    plan_json.write_text(json.dumps(result["after_probe_plan"], ensure_ascii=False, indent=2), encoding="utf-8")
    plan_md.write_text(render_after_probe_plan_markdown(result, plan_df), encoding="utf-8")
    return {
        "probe_csv": csv_path,
        "probe_json": json_path,
        "probe_md": md_path,
        "plan_json": plan_json,
        "plan_md": plan_md,
    }


def render_p0_probe_markdown(result: dict[str, Any], probe_df: pd.DataFrame) -> str:
    counts = probe_df["rqdata_probe_status"].value_counts(dropna=False).to_dict() if not probe_df.empty else {}
    lines = [
        "# P0 Missing Raw Fields RQData Probe",
        "",
        f"Generated at: `{result['generated_at']}`",
        f"RQData probe enabled: `{result['rqdata_probe_enabled']}`",
        f"P0 fields selected: `{result['p0_field_count']}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in sorted(counts.items()):
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## By Data Pack", ""])
    summary = probe_df.groupby(["data_pack", "rqdata_probe_status"]).size().reset_index(name="count") if not probe_df.empty else pd.DataFrame()
    lines.extend(_markdown_table(summary, ["data_pack", "rqdata_probe_status", "count"]))
    lines.extend(["", "## Field Results", ""])
    lines.extend(_markdown_table(probe_df, ["data_pack", "canonical_field", "rqdata_probe_status", "sample_row_count", "sample_non_null_count", "recommended_action_after_probe"]))
    return "\n".join(lines) + "\n"


def render_after_probe_plan_markdown(result: dict[str, Any], plan_df: pd.DataFrame) -> str:
    lines = [
        "# Research Report Backfill Plan After P0 Probe",
        "",
        f"Generated at: `{result['generated_at']}`",
        "",
    ]
    lines.extend(_markdown_table(plan_df, AFTER_PROBE_PLAN_COLUMNS))
    return "\n".join(lines) + "\n"


def sanitize_error_message(message: str) -> str:
    secrets = [
        settings.rqdata_license or "",
        os.environ.get("RQDATAC_KEY") or "",
        os.environ.get("RQDATA_LICENSE") or "",
    ]
    sanitized = str(message)
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "<redacted>")
    sanitized = re.sub(r"(?i)(token|license|password|key)=?[A-Za-z0-9_\\-]{12,}", r"\1=<redacted>", sanitized)
    sanitized = re.sub(r"[A-Za-z0-9_\\-]{32,}", "<redacted>", sanitized)
    return sanitized[:500]


def _base_output_row(row: dict[str, Any]) -> dict[str, Any]:
    sample_start, sample_end = _sample_range(row)
    return {
        "priority": row.get("priority", ""),
        "data_pack": row.get("data_pack", ""),
        "canonical_field": row.get("canonical_field", ""),
        "chinese_name": row.get("chinese_name", ""),
        "field_type": row.get("field_type", ""),
        "required_frequency": row.get("required_frequency", ""),
        "local_status": row.get("local_status", ""),
        "rqdata_probe_status": "not_probed",
        "rqdata_candidate_function": row.get("rqdata_candidate_function", ""),
        "rqdata_candidate_field": row.get("rqdata_candidate_field", ""),
        "rqdata_frequency": _rqdata_frequency(row),
        "sample_start": sample_start,
        "sample_end": sample_end,
        "sample_symbols": ",".join(PROBE_SYMBOLS),
        "sample_row_count": 0,
        "sample_non_null_count": 0,
        "sample_non_null_ratio": 0.0,
        "permission_status": "not_checked",
        "error_type": "",
        "error_message_sanitized": "",
        "recommended_action_after_probe": "source_audit_needed",
        "recommended_dataset_name": row.get("recommended_dataset_name", ""),
        "notes": row.get("notes", ""),
    }


def _not_probed_row(row: dict[str, Any]) -> dict[str, Any]:
    base = _base_output_row(row)
    base["recommended_action_after_probe"] = "source_audit_needed"
    return base


def _status_from_sample(row_count: int, non_null_count: int) -> str:
    if row_count <= 0:
        return "available_but_empty_sample"
    if non_null_count <= 0:
        return "available_but_empty_sample"
    return "available"


def _count_non_null(frame: pd.DataFrame, field: str) -> int:
    if frame is None or len(frame) == 0:
        return 0
    if field in frame.columns:
        return int(frame[field].notna().sum())
    if len(frame.columns) == 1:
        return int(frame.iloc[:, 0].notna().sum())
    numeric_cols = frame.select_dtypes(include="number").columns
    if len(numeric_cols):
        return int(frame[numeric_cols[0]].notna().sum())
    return int(len(frame))


def _ensure_frame(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame(value)


def _function_status_or_failed(row: dict[str, Any], exc: Exception) -> str:
    if isinstance(exc, AttributeError):
        return "function_not_found"
    text = str(exc).lower()
    if "not found" in text or "no attribute" in text:
        return "function_not_found"
    if "unknown" in text or "invalid" in text or "not exist" in text:
        return "unavailable"
    return "probe_failed"


def _recommended_action(status: str) -> str:
    if status == "available":
        return "backfill_p0"
    if status == "permission_required":
        return "source_audit_needed"
    if status == "function_not_found":
        return "external_source_required"
    if status in {"available_but_empty_sample", "unavailable", "probe_failed", "quota_limited"}:
        return "source_audit_needed"
    return "source_audit_needed"


def _sample_range(row: dict[str, Any]) -> tuple[str, str]:
    pack = row.get("data_pack", "")
    if pack == "valuation_core":
        return PROBE_DATES[0], VALUATION_EXTRA_DATES[-1]
    if pack == "financial_pit_core":
        return "2024q4", "2025q4"
    return PROBE_DATES[-1], PROBE_DATES[-1]


def _rqdata_frequency(row: dict[str, Any]) -> str:
    pack = row.get("data_pack", "")
    if pack == "financial_pit_core":
        return "quarterly PIT"
    if pack == "corporate_actions_dividend_share_capital":
        return "event/month_end"
    return str(row.get("required_frequency") or "")


def _industry_source_and_level(field: str) -> tuple[str, int]:
    if field.startswith("sw_"):
        return "shenwan_2021", int(field[-1])
    if field.startswith("citics_"):
        return "citics_2019", int(field[-1])
    if field.startswith("csi_"):
        return "zjw", int(field[-1])
    return "citics_2019", 1


def _unlocked_derived_fields(pack: str, probe_df: pd.DataFrame, derived_df: pd.DataFrame) -> str:
    available_fields = set(probe_df.loc[probe_df["rqdata_probe_status"] == "available", "canonical_field"])
    if not available_fields or derived_df.empty:
        return ""
    unlocked = []
    for row in derived_df.to_dict(orient="records"):
        deps = [dep.split(".")[-1] for dep in str(row.get("required_raw_fields", "")).split(",") if dep]
        missing = [dep for dep in deps if dep in set(probe_df["canonical_field"]) and dep not in available_fields]
        if deps and not missing and any(dep in available_fields for dep in deps):
            unlocked.append(str(row.get("derived_field", "")))
    return ",".join(sorted(set(unlocked)))


def _recommended_storage_frequency(pack: str) -> str:
    return {
        "valuation_core": "daily + month_end snapshot",
        "financial_pit_core": "quarterly PIT",
        "corporate_actions_dividend_share_capital": "event + month_end snapshot",
        "index_universe_extended": "daily/month_end",
        "industry_taxonomy": "version table or daily mapping",
        "daily_market_core": "daily",
    }.get(pack, "")


def _recommended_scope(pack: str) -> str:
    return {
        "valuation_core": "2016-present A-share daily/month-end missing fields",
        "financial_pit_core": "2015-present A-share quarterly PIT expanded fields",
        "corporate_actions_dividend_share_capital": "2016-present A-share corporate action events and month-end share capital",
        "index_universe_extended": "2016-present selected broad/theme index membership",
        "industry_taxonomy": "2016-present selected industry taxonomy mappings",
        "daily_market_core": "2016-present daily market core gap fields",
    }.get(pack, "source-specific")


def _storage_level(pack: str) -> str:
    return {
        "valuation_core": "large",
        "financial_pit_core": "medium",
        "corporate_actions_dividend_share_capital": "medium",
        "index_universe_extended": "medium",
        "industry_taxonomy": "medium",
        "daily_market_core": "large",
    }.get(pack, "medium")


def _permission_risk(pack_df: pd.DataFrame) -> str:
    statuses = set(pack_df["rqdata_probe_status"])
    if "permission_required" in statuses:
        return "high"
    if statuses & {"probe_failed", "unavailable", "function_not_found"}:
        return "medium"
    return "low"


def _go_or_no_go(pack_df: pd.DataFrame) -> str:
    statuses = set(pack_df["rqdata_probe_status"])
    if "available" in statuses and "permission_required" not in statuses:
        return "GO"
    if statuses <= {"function_not_found", "unavailable", "available_but_empty_sample", "probe_failed", "not_probed"}:
        return "NO-GO"
    return "CONDITIONAL GO"


def _recommended_next_stage(pack: str, go: str) -> str:
    if go == "GO":
        return {
            "valuation_core": "Stage 34B: Valuation Core Missing Field Backfill",
            "financial_pit_core": "Stage 34B: Financial PIT Core Field Pack Expansion",
            "corporate_actions_dividend_share_capital": "Stage 34A: Corporate Actions + Dividends + Share Capital",
            "index_universe_extended": "Stage 34C: Index Universe Extended + Industry Taxonomy",
            "industry_taxonomy": "Stage 34C: Index Universe Extended + Industry Taxonomy",
            "daily_market_core": "Stage 34D: Daily Market Core Gap Backfill",
        }.get(pack, "Stage 34: P0 Data Pack Backfill")
    return "Source audit before backfill"


def _plan_notes(pack: str, pack_df: pd.DataFrame) -> str:
    empty_count = int((pack_df["rqdata_probe_status"] == "available_but_empty_sample").sum())
    if empty_count:
        return f"{empty_count} fields returned empty sample; verify sample date or source semantics before backfill."
    if pack == "corporate_actions_dividend_share_capital":
        return "Event APIs often need a separate source audit even if some daily factor fields are available."
    return ""


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
        lines.append("| " + " | ".join(str(row[column]).replace("|", "\\|") for column in columns) + " |")
    return lines
