from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.settings import settings


CORE_DATASETS = [
    "instruments",
    "trading_calendar",
    "prices_1d_none",
    "prices_1d_pre",
    "index_prices_1d",
    "tradability_1d",
    "valuation_1d",
    "industry_classification",
    "index_components",
    "index_weights",
    "intraday_snapshots",
]

HXZ_REQUIREMENTS = [
    {
        "requirement": "monthly_total_return",
        "needed_for": "Rm-Rf / ME / IA / ROE portfolio returns",
        "local_status": "derivable",
        "local_dataset": "prices_1d_none",
        "local_fields": "trade_date, order_book_id, close",
        "gap": "daily return and monthly total return are not materialized; derive from unadjusted close with corporate-action checks.",
        "priority": "P0",
    },
    {
        "requirement": "previous_month_end_market_cap",
        "needed_for": "size split and value-weighted portfolio returns",
        "local_status": "available",
        "local_dataset": "valuation_1d",
        "local_fields": "market_cap, float_market_cap",
        "gap": "share-count provenance and units need RQData confirmation.",
        "priority": "P0",
    },
    {
        "requirement": "annual_total_assets",
        "needed_for": "investment factor IA",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "local parquet missing; RQData get_factor candidates include total_assets, total_assets_lyr_0, and total_assets_mrq_0, but announce-date semantics still need validation.",
        "priority": "P0",
    },
    {
        "requirement": "prior_year_total_assets",
        "needed_for": "investment factor IA",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "derive from total_assets_lyr_0 or materialized annual total assets after PIT semantics are validated.",
        "priority": "P0",
    },
    {
        "requirement": "single_quarter_profit",
        "needed_for": "profitability factor ROE",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "local parquet missing; RQData get_factor candidates include net_profit_parent_company_mrq_0 and adjusted_net_profit_mrq_0, but quarter convention needs validation.",
        "priority": "P0",
    },
    {
        "requirement": "previous_quarter_book_equity",
        "needed_for": "profitability factor ROE denominator",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "local parquet missing; RQData get_factor candidates include equity_parent_company_mrq_0 and total_equity_mrq_0, but announce-date semantics still need validation.",
        "priority": "P0",
    },
    {
        "requirement": "real_announcement_date",
        "needed_for": "point-in-time no-lookahead accounting data",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "not found in get_all_factor_names keyword searches for announce, announcement, pub, or report.",
        "priority": "P0",
    },
    {
        "requirement": "industry_and_financial_flag",
        "needed_for": "financial exclusion / industry diagnostics",
        "local_status": "available",
        "local_dataset": "industry_classification, instruments",
        "local_fields": "industry_system, industry_level, industry_code, industry_name, sector_code",
        "gap": "financial flag can be derived, but HXZ replication rule must choose a canonical industry system.",
        "priority": "P0",
    },
    {
        "requirement": "positive_negative_book_equity",
        "needed_for": "accounting data filters",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "depends on book equity backfill.",
        "priority": "P0",
    },
    {
        "requirement": "listing_delisting_status",
        "needed_for": "universe and survivorship control",
        "local_status": "partial",
        "local_dataset": "instruments, tradability_1d",
        "local_fields": "listed_date, de_listed_date, status, is_listed, is_suspended, is_st",
        "gap": "static instruments plus daily tradability exist; full status history semantics need probe.",
        "priority": "P1",
    },
    {
        "requirement": "a_share_market_return",
        "needed_for": "market factor Rm-Rf",
        "local_status": "derivable",
        "local_dataset": "prices_1d_none, valuation_1d, index_prices_1d",
        "local_fields": "close, market_cap, index close",
        "gap": "HXZ all-A value-weighted market return should be materialized and reconciled against broad indices.",
        "priority": "P0",
    },
    {
        "requirement": "rmb_risk_free_rate",
        "needed_for": "excess return factors",
        "local_status": "missing",
        "local_dataset": "",
        "local_fields": "",
        "gap": "not found in get_all_factor_names keyword searches for risk_free, rf, shibor, or treasury-rate style names.",
        "priority": "P0",
    },
]


def build_hxz_audit(data_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    datasets = {dataset: _summarize_dataset(root, dataset) for dataset in CORE_DATASETS}
    cross = _build_cross_checks(root)
    matrix = _build_field_matrix(datasets)
    return {
        "data_root": str(root),
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "datasets": datasets,
        "cross_checks": cross,
        "hxz_field_matrix": matrix,
        "local_readiness": _judge_readiness(matrix),
        "backfill_plan": _build_backfill_plan(matrix),
    }


def write_hxz_audit_outputs(
    audit: dict[str, Any],
    output_dir: str | Path = "reports/data_audit",
    manifest_dir: str | Path | None = None,
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    manifest_root = (
        Path(manifest_dir)
        if manifest_dir is not None
        else settings.data_root_path / "manifests"
    )
    manifest_root.mkdir(parents=True, exist_ok=True)

    json_path = output / "hxz_data_audit.json"
    md_path = output / "hxz_data_audit.md"
    matrix_path = output / "hxz_field_matrix.csv"
    plan_path = output / "hxz_backfill_plan.json"
    reconcile_path = output / "hxz_reconciliation.md"
    manifest_path = manifest_root / "hxz_backfill_manifest.json"

    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(audit["hxz_field_matrix"]).to_csv(matrix_path, index=False)
    plan_path.write_text(json.dumps(audit["backfill_plan"], ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(_manifest_from_plan(audit), ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_hxz_audit_markdown(audit), encoding="utf-8")
    reconcile_path.write_text(render_hxz_reconciliation_markdown(audit), encoding="utf-8")
    return {
        "audit_json": json_path,
        "audit_md": md_path,
        "field_matrix_csv": matrix_path,
        "backfill_plan_json": plan_path,
        "backfill_manifest_json": manifest_path,
        "reconciliation_md": reconcile_path,
    }


def render_hxz_audit_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# HXZ Data Audit",
        "",
        f"Data root: `{audit['data_root']}`",
        f"Generated at: `{audit['generated_at']}`",
        "",
        "## Verdict",
        "",
        audit["local_readiness"]["summary"],
        "",
        "## Dataset Coverage",
        "",
        "| dataset | files | rows | symbols | date range | duplicate keys | key columns |",
        "| --- | ---: | ---: | ---: | --- | ---: | --- |",
    ]
    for dataset, info in audit["datasets"].items():
        lines.append(
            "| {dataset} | {files} | {rows} | {symbols} | {date_range} | {dupes} | {keys} |".format(
                dataset=dataset,
                files=info["file_count"],
                rows=info["rows"],
                symbols=info.get("symbols") or "",
                date_range=_range_text(info.get("min_date"), info.get("max_date")),
                dupes=info.get("duplicate_keys"),
                keys=", ".join(info.get("key_columns") or []),
            )
        )

    lines.extend(["", "## HXZ Field Matrix", ""])
    lines.append("| requirement | status | local dataset | fields | priority | gap |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for item in audit["hxz_field_matrix"]:
        lines.append(
            f"| {item['requirement']} | {item['local_status']} | {item['local_dataset']} | "
            f"{item['local_fields']} | {item['priority']} | {item['gap']} |"
        )

    lines.extend(["", "## Cross Checks", ""])
    for check in audit["cross_checks"]:
        lines.append(f"- {check['name']}: {check['status']} ({check['details']})")

    lines.extend(["", "## Immediate Missing P0 Data", ""])
    for item in audit["backfill_plan"]["items"]:
        if item["priority"] == "P0":
            lines.append(f"- {item['dataset']}: {item['reason']}")
    return "\n".join(lines) + "\n"


def render_hxz_reconciliation_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# HXZ Reconciliation",
        "",
        "This file reconciles current local data against the minimum inputs needed for China HXZ four-factor replication.",
        "",
        "## Current Local State",
        "",
    ]
    for dataset, info in audit["datasets"].items():
        lines.append(
            f"- `{dataset}`: rows={info['rows']}, symbols={info.get('symbols')}, "
            f"range={_range_text(info.get('min_date'), info.get('max_date'))}, files={info['file_count']}"
        )
    lines.extend(["", "## Blocking Gaps", ""])
    for item in audit["hxz_field_matrix"]:
        if item["local_status"] == "missing":
            lines.append(f"- `{item['requirement']}`: {item['gap']}")
    lines.extend(["", "## Probe Dependency", ""])
    lines.append(
        "RQData small-sample probing is still required to confirm financial statement APIs, "
        "announcement-date semantics, cumulative versus single-quarter fields, and risk-free source availability."
    )
    return "\n".join(lines) + "\n"


def _summarize_dataset(root: Path, dataset: str) -> dict[str, Any]:
    dataset_root = root / dataset
    files = _dataset_files(dataset_root)
    info: dict[str, Any] = {
        "dataset": dataset,
        "path": str(dataset_root),
        "exists": dataset_root.exists(),
        "file_count": len(files),
        "rows": 0,
        "symbols": None,
        "min_date": None,
        "max_date": None,
        "columns": [],
        "dtypes": {},
        "key_columns": [],
        "duplicate_keys": 0,
        "null_rates": {},
        "partitions": [],
        "errors": [],
    }
    symbol_values: set[str] = set()
    min_dates: list[pd.Timestamp] = []
    max_dates: list[pd.Timestamp] = []
    null_counts: dict[str, int] = {}
    non_null_base: dict[str, int] = {}

    for file_path in files:
        try:
            frame = pd.read_parquet(file_path)
        except Exception as exc:
            info["errors"].append({"file": str(file_path), "error": f"{type(exc).__name__}: {exc}"})
            continue

        if not info["columns"]:
            info["columns"] = list(frame.columns)
            info["dtypes"] = {col: str(dtype) for col, dtype in frame.dtypes.items()}
            info["key_columns"] = _key_columns(frame)
        rows = int(len(frame))
        info["rows"] += rows
        if "order_book_id" in frame.columns:
            symbol_values.update(frame["order_book_id"].dropna().astype(str).unique().tolist())
        file_min, file_max = _date_bounds(frame)
        if file_min is not None:
            min_dates.append(file_min)
        if file_max is not None:
            max_dates.append(file_max)
        keys = _key_columns(frame)
        duplicate_keys = int(frame.duplicated(keys).sum()) if keys else 0
        info["duplicate_keys"] += duplicate_keys
        for col in frame.columns:
            null_counts[col] = null_counts.get(col, 0) + int(frame[col].isna().sum())
            non_null_base[col] = non_null_base.get(col, 0) + rows
        partition = _partition_info(file_path)
        partition.update(
            {
                "file": str(file_path),
                "rows": rows,
                "symbols": int(frame["order_book_id"].nunique()) if "order_book_id" in frame.columns else None,
                "min_date": file_min.strftime("%Y-%m-%d") if file_min is not None else None,
                "max_date": file_max.strftime("%Y-%m-%d") if file_max is not None else None,
                "duplicate_keys": duplicate_keys,
            }
        )
        info["partitions"].append(partition)

    if symbol_values:
        info["symbols"] = len(symbol_values)
    if min_dates:
        info["min_date"] = min(min_dates).strftime("%Y-%m-%d")
    if max_dates:
        info["max_date"] = max(max_dates).strftime("%Y-%m-%d")
    info["null_rates"] = {
        col: round(null_counts[col] / non_null_base[col], 6)
        for col in sorted(null_counts)
        if non_null_base.get(col)
    }
    return info


def _build_cross_checks(root: Path) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    prices = _read_years(root / "prices_1d_none")
    valuation = _read_years(root / "valuation_1d")
    tradability = _read_years(root / "tradability_1d")
    if prices is not None and valuation is not None:
        checks.append(_key_overlap_check("prices_vs_valuation", prices, valuation))
    if prices is not None and tradability is not None:
        checks.append(_key_overlap_check("prices_vs_tradability", prices, tradability))
    instruments_path = root / "instruments" / "instruments.parquet"
    if instruments_path.exists():
        instruments = pd.read_parquet(instruments_path)
        financial_count = int(
            instruments.get("sector_code", pd.Series(dtype=str)).astype(str).eq("Financials").sum()
        )
        st_count = int(instruments.get("special_type", pd.Series(dtype=str)).astype(str).ne("Normal").sum())
        checks.append(
            {
                "name": "instrument_financial_and_special_type",
                "status": "ok",
                "details": f"financial_instruments={financial_count}, non_normal_special_type={st_count}",
            }
        )
    return checks


def _key_overlap_check(name: str, left: pd.DataFrame, right: pd.DataFrame) -> dict[str, str]:
    keys = ["trade_date", "order_book_id"]
    left_keys = left[keys].drop_duplicates()
    right_keys = right[keys].drop_duplicates()
    merged = left_keys.merge(right_keys, on=keys, how="outer", indicator=True)
    left_only = int((merged["_merge"] == "left_only").sum())
    right_only = int((merged["_merge"] == "right_only").sum())
    status = "ok" if left_only == 0 and right_only == 0 else "warning"
    return {
        "name": name,
        "status": status,
        "details": f"left_only={left_only}, right_only={right_only}, overlap={int((merged['_merge'] == 'both').sum())}",
    }


def _read_years(path: Path) -> pd.DataFrame | None:
    files = sorted(path.glob("year=*.parquet"))
    if not files:
        return None
    frames = [pd.read_parquet(file, columns=["trade_date", "order_book_id"]) for file in files]
    return pd.concat(frames, ignore_index=True)


def _build_field_matrix(datasets: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for item in HXZ_REQUIREMENTS:
        record = dict(item)
        dataset = item["local_dataset"].split(",", 1)[0].strip()
        record["evidence"] = ""
        if dataset and dataset in datasets:
            info = datasets[dataset]
            record["evidence"] = (
                f"rows={info['rows']}, symbols={info.get('symbols')}, "
                f"range={_range_text(info.get('min_date'), info.get('max_date'))}"
            )
        output.append(record)
    return output


def _judge_readiness(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    missing = [item for item in matrix if item["local_status"] == "missing"]
    partial = [item for item in matrix if item["local_status"] in {"partial", "derivable"}]
    return {
        "ready_for_full_hxz_replication": False,
        "missing_count": len(missing),
        "partial_or_derivable_count": len(partial),
        "summary": (
            "Local A-share daily market data is strong enough for returns, market-cap sorts, "
            "tradability filters, and industry diagnostics, but it is not yet sufficient for a "
            "credible China HXZ four-factor replication because PIT financial statement fields, "
            "announcement dates, book equity, quarterly profit, and RMB risk-free rate are missing."
        ),
    }


def _build_backfill_plan(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "dataset": "financial_balance_sheet_pit",
            "priority": "P0",
            "reason": "annual total assets, prior-year total assets, book equity / parent equity, announce date",
            "target_fields": [
                "total_assets",
                "total_assets_lyr_0",
                "total_assets_mrq_0",
                "total_equity_mrq_0",
                "equity_parent_company_mrq_0",
                "equity_parent_company_lyr_0",
                "announce_date_unresolved",
            ],
            "write_mode": "year partition, incremental append + deduplicate, no overwrite unless explicit",
        },
        {
            "dataset": "financial_income_statement_pit",
            "priority": "P0",
            "reason": "single-quarter profit and parent net profit for ROE",
            "target_fields": [
                "net_profit_parent_company_mrq_0",
                "net_profit_parent_company_lyr_0",
                "adjusted_net_profit_mrq_0",
                "adjusted_net_profit_lyr_0",
                "announce_date_unresolved",
            ],
            "write_mode": "year partition, cumulative-to-quarterly conversion audited separately",
        },
        {
            "dataset": "risk_free_rate",
            "priority": "P0",
            "reason": "RMB risk-free rate for excess returns",
            "target_fields": ["trade_date", "rate", "rate_type", "source"],
            "write_mode": "single or yearly parquet after source convention is confirmed",
        },
        {
            "dataset": "monthly_hxz_inputs",
            "priority": "P0",
            "reason": "materialized monthly returns, previous month-end ME, accounting lags, and filters",
            "target_fields": ["month", "order_book_id", "ret", "me_lag", "roe", "ia", "rf", "is_financial"],
            "write_mode": "derived local dataset after raw fields pass validation",
        },
        {
            "dataset": "security_status_history",
            "priority": "P1",
            "reason": "survivorship and ST/listing/delisting status reconciliation",
            "target_fields": ["trade_date", "order_book_id", "status", "special_type", "is_st", "is_listed"],
            "write_mode": "derive from instruments/tradability and probe RQData status history if available",
        },
    ]
    return {
        "plan_status": "draft_after_local_audit",
        "rqdata_probe_required_before_backfill": True,
        "items": items,
        "field_matrix_missing": [item for item in matrix if item["local_status"] == "missing"],
    }


def _manifest_from_plan(audit: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest_name": "hxz_backfill_manifest",
        "data_root": audit["data_root"],
        "created_at": audit["generated_at"],
        "status": "draft_pending_rqdata_probe",
        "do_not_overwrite_existing_core_daily_partitions": True,
        "target_date_range": {
            "start": audit["datasets"].get("prices_1d_none", {}).get("min_date"),
            "end": audit["datasets"].get("prices_1d_none", {}).get("max_date"),
        },
        "datasets": audit["backfill_plan"]["items"],
    }


def _dataset_files(dataset_root: Path) -> list[Path]:
    if not dataset_root.exists():
        return []
    return sorted(dataset_root.rglob("*.parquet"))


def _date_bounds(frame: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    date_col = next((col for col in ["trade_date", "datetime", "listed_date"] if col in frame.columns), None)
    if date_col is None or frame.empty:
        return None, None
    dates = pd.to_datetime(frame[date_col], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min(), dates.max()


def _key_columns(frame: pd.DataFrame) -> list[str]:
    for keys in [
        ["trade_date", "snapshot_time", "order_book_id"],
        ["trade_date", "index_id", "order_book_id"],
        ["trade_date", "order_book_id", "adjust_type"],
        ["trade_date", "order_book_id", "industry_system", "industry_level"],
        ["trade_date", "order_book_id"],
        ["trade_date"],
        ["order_book_id"],
    ]:
        if set(keys).issubset(frame.columns):
            return keys
    return []


def _partition_info(path: Path) -> dict[str, int | None]:
    year = None
    month = None
    for part in path.parts:
        if part.startswith("year="):
            year = int(Path(part).stem.split("=", 1)[1])
        if part.startswith("month="):
            month = int(Path(part).stem.split("=", 1)[1])
    return {"year": year, "month": month}


def _range_text(start: str | None, end: str | None) -> str:
    if not start or not end:
        return ""
    return f"{start} to {end}"
