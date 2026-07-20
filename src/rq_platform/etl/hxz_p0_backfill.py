from __future__ import annotations

import hashlib
import json
import math
import os
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.hxz_p0_quality import (
    check_financial_factor_daily_pit,
    check_financial_pit_quarterly,
    check_risk_free_rate,
)
from rq_platform.settings import settings


DATASETS = ["financial_pit_quarterly", "financial_factor_daily_pit", "risk_free_rate"]

PIT_FIELDS = ["total_assets", "equity_parent_company", "total_equity", "net_profit_parent_company"]
FACTOR_FIELDS = [
    "total_assets_mrq_0",
    "total_assets_lyr_0",
    "equity_parent_company_mrq_0",
    "equity_parent_company_lyr_0",
    "total_equity_mrq_0",
    "net_profit_parent_company_mrq_0",
    "net_profit_parent_company_lyr_0",
]
AUX_FACTOR_FIELDS = ["adjusted_net_profit_mrq_0", "adjusted_net_profit_lyr_0"]
RISK_FREE_FIELDS = ["0S", "1M", "3M", "1Y"]

STATUS_COLUMNS = [
    "run_id",
    "dataset",
    "mode",
    "chunk_id",
    "symbol_start",
    "symbol_end",
    "symbol_count",
    "range_start",
    "range_end",
    "planned_calls",
    "actual_calls",
    "returned_rows",
    "status",
    "started_at",
    "finished_at",
    "error_type",
    "error_message_sanitized",
    "retryable",
    "output_path",
    "checksum",
]


@dataclass(frozen=True)
class HXZP0Task:
    dataset: str
    source_api: str
    target_path: str
    requested_fields: list[str]
    start_date: str | None
    end_date: str | None
    start_quarter: str | None
    end_quarter: str | None
    total_symbols: int
    symbol_batch_size: int
    date_or_quarter_chunk_size: int
    estimated_chunks: int
    estimated_api_calls: int
    estimated_rows: int
    rough_disk_size: str
    existing_partitions: list[str]
    missing_partitions: list[str]
    write_mode: str
    resume_key: str
    quality_checks: list[str]
    status: str
    blocked_reason: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def build_hxz_p0_plan(
    *,
    datasets: list[str] | str = "all",
    start_date: str = "2016-01-04",
    end_date: str | None = None,
    start_quarter: str = "2015q4",
    end_quarter: str | None = None,
    symbol_batch_size: int = 200,
    date_chunk_size: int = 252,
    quarter_chunk_size: int = 4,
    data_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    selected = _normalize_datasets(datasets)
    end_date = end_date or _latest_data_date(root) or "2026-07-14"
    end_quarter = end_quarter or _quarter_for_date(end_date)
    symbols = _load_symbols(root)
    trading_dates = _load_trading_dates(root, start_date, end_date)
    quarters = _quarters_between(start_quarter, end_quarter)
    run_id = f"hxz_p0_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

    tasks = [
        task
        for dataset in selected
        for task in [
            _build_task(
                dataset=dataset,
                root=root,
                symbols=symbols,
                trading_dates=trading_dates,
                quarters=quarters,
                start_date=start_date,
                end_date=end_date,
                start_quarter=start_quarter,
                end_quarter=end_quarter,
                symbol_batch_size=symbol_batch_size,
                date_chunk_size=date_chunk_size,
                quarter_chunk_size=quarter_chunk_size,
            )
        ]
    ]
    return {
        "run_id": run_id,
        "mode": "dry_run",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "data_root": str(root),
        "datasets": [task.to_dict() for task in tasks],
        "summary": {
            "dataset_count": len(tasks),
            "total_estimated_api_calls": sum(task.estimated_api_calls for task in tasks),
            "total_estimated_rows": sum(task.estimated_rows for task in tasks),
            "symbols": len(symbols),
            "trading_dates": len(trading_dates),
            "quarters": len(quarters),
        },
    }


def write_hxz_p0_dry_run_report(
    plan: dict[str, Any],
    *,
    output_dir: str | Path = "reports/data_audit",
) -> dict[str, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "hxz_p0_dry_run.json"
    md_path = output / "hxz_p0_dry_run.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_hxz_p0_plan_markdown(plan), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def render_hxz_p0_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# HXZ P0 Backfill Dry Run",
        "",
        f"run_id: `{plan['run_id']}`",
        f"data_root: `{plan['data_root']}`",
        f"created_at: `{plan['created_at']}`",
        "",
        "## Summary",
        "",
        f"- datasets: {plan['summary']['dataset_count']}",
        f"- symbols: {plan['summary']['symbols']}",
        f"- trading_dates: {plan['summary']['trading_dates']}",
        f"- quarters: {plan['summary']['quarters']}",
        f"- estimated_api_calls: {plan['summary']['total_estimated_api_calls']}",
        f"- estimated_rows: {plan['summary']['total_estimated_rows']}",
        "",
        "## Dataset Plans",
        "",
        "| dataset | source_api | target_path | chunks | calls | rows | rough_disk | write_mode | status |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for item in plan["datasets"]:
        lines.append(
            f"| {item['dataset']} | {item['source_api']} | `{item['target_path']}` | "
            f"{item['estimated_chunks']} | {item['estimated_api_calls']} | {item['estimated_rows']} | "
            f"{item['rough_disk_size']} | {item['write_mode']} | {item['status']} |"
        )
    lines.extend(["", "## Quality Checks", ""])
    for item in plan["datasets"]:
        lines.append(f"### {item['dataset']}")
        for check in item["quality_checks"]:
            lines.append(f"- {check}")
        lines.append("")
    return "\n".join(lines)


def append_hxz_status(status_path: str | Path, record: dict[str, Any]) -> None:
    path = Path(status_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: record.get(column, "") for column in STATUS_COLUMNS}
    frame = pd.DataFrame([row], columns=STATUS_COLUMNS)
    frame.to_csv(path, mode="a", header=not path.exists(), index=False)


def load_hxz_status(status_path: str | Path) -> pd.DataFrame:
    path = Path(status_path)
    if not path.exists():
        return pd.DataFrame(columns=STATUS_COLUMNS)
    return pd.read_csv(path)


def write_planned_status(plan: dict[str, Any], status_path: str | Path | None = None) -> Path:
    path = Path(status_path) if status_path else settings.data_root_path / "update_logs" / "hxz_p0_backfill_status.csv"
    now = datetime.now().isoformat(timespec="seconds")
    for idx, task in enumerate(plan["datasets"], start=1):
        append_hxz_status(
            path,
            {
                "run_id": plan["run_id"],
                "dataset": task["dataset"],
                "mode": "dry_run",
                "chunk_id": f"plan-{idx}",
                "symbol_count": task["total_symbols"],
                "range_start": task.get("start_date") or task.get("start_quarter"),
                "range_end": task.get("end_date") or task.get("end_quarter"),
                "planned_calls": task["estimated_api_calls"],
                "actual_calls": 0,
                "returned_rows": 0,
                "status": "planned",
                "started_at": now,
                "finished_at": now,
                "retryable": False,
                "output_path": task["target_path"],
                "checksum": _checksum(json.dumps(task, sort_keys=True)),
            },
        )
    return path


def update_hxz_backfill_plan_file(
    plan: dict[str, Any],
    *,
    path: str | Path = "reports/data_audit/hxz_backfill_plan.json",
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "plan_status": "dry_run_ready",
        "rqdata_probe_required_before_backfill": False,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "stage": "HXZ-P0 Backfill Dry Run",
        "items": plan["datasets"],
        "future_derived_stage": {
            "dataset": "monthly_hxz_inputs",
            "status": "deferred",
            "reason": "derived factor construction is out of scope for P0 raw backfill dry-run",
        },
        "smoke_result": "pending_or_recorded_in_hxz_p0_smoke_validation",
        "blockers": [
            "formal full backfill not approved in this stage",
            "PIT cross-validation must pass on smoke before production writes",
        ],
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def record_hxz_smoke_in_plan(
    smoke_result: dict[str, Any],
    *,
    path: str | Path = "reports/data_audit/hxz_backfill_plan.json",
) -> Path:
    output_path = Path(path)
    data: dict[str, Any] = {}
    if output_path.exists():
        data = json.loads(output_path.read_text(encoding="utf-8"))
    data["plan_status"] = "dry_run_validated" if smoke_result.get("status") == "success" else "dry_run_ready"
    data["smoke_result"] = {
        "status": smoke_result.get("status"),
        "rqdata_calls": smoke_result.get("rqdata_calls", 0),
        "financial_factor_daily_pit_rows": smoke_result.get("datasets", {})
        .get("financial_factor_daily_pit", {})
        .get("rows"),
        "financial_pit_quarterly_rows": smoke_result.get("datasets", {})
        .get("financial_pit_quarterly", {})
        .get("rows"),
        "risk_free_rate_rows": smoke_result.get("datasets", {}).get("risk_free_rate", {}).get("rows"),
        "pit_cross_validation": smoke_result.get("datasets", {}).get("pit_cross_validation", {}),
    }
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return output_path


def run_hxz_p0_smoke(
    *,
    output_dir: str | Path = "reports/data_audit",
    symbols: list[str] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    symbols = symbols or ["600519.XSHG", "000001.XSHE", "300750.XSHE", "688001.XSHG"]
    token = os.getenv("RQDATAC_KEY") or settings.rqdata_license
    if not token:
        result = {
            "status": "blocked",
            "reason": "RQDATAC_KEY/RQDATA_LICENSE is not set in this shell. No RQData call was made.",
            "rqdata_calls": 0,
            "datasets": {},
        }
        _write_smoke_report(result, output)
        return result

    try:
        import rqdatac  # type: ignore
    except Exception as exc:
        result = {
            "status": "failed",
            "reason": f"rqdatac import failed: {type(exc).__name__}: {exc}",
            "rqdata_calls": 0,
            "datasets": {},
        }
        _write_smoke_report(result, output)
        return result

    rqdatac.init(username="license", password=token)
    datasets: dict[str, Any] = {}
    calls = 0

    factor_fields = FACTOR_FIELDS + AUX_FACTOR_FIELDS
    factor = rqdatac.get_factor(symbols, factor_fields, start_date="2025-01-02", end_date="2025-01-10", expect_df=True)
    calls += 1
    factor_frame = factor.reset_index().rename(columns={"date": "trade_date"})
    datasets["financial_factor_daily_pit"] = _frame_summary(factor_frame, ["order_book_id", "trade_date"], factor_fields)
    datasets["financial_factor_daily_pit"]["quality_issues"] = [
        issue.to_dict() for issue in check_financial_factor_daily_pit(factor_frame)
    ]

    pit = rqdatac.get_pit_financials_ex(
        order_book_ids=symbols,
        fields=PIT_FIELDS,
        start_quarter="2024q3",
        end_quarter="2024q4",
        date="2025-01-10",
        statements="latest",
        market="cn",
    )
    calls += 1
    pit_frame = pit.reset_index()
    datasets["financial_pit_quarterly"] = _frame_summary(
        pit_frame,
        ["order_book_id", "quarter", "info_date"],
        ["info_date", "rice_create_tm", "if_adjusted"] + PIT_FIELDS,
    )
    datasets["financial_pit_quarterly"]["quality_issues"] = [
        issue.to_dict() for issue in check_financial_pit_quarterly(pit_frame)
    ]
    datasets["financial_pit_quarterly"]["version_policy"] = _pit_version_policy(rqdatac, symbols)
    calls += datasets["financial_pit_quarterly"]["version_policy"].get("actual_calls", 0)

    risk_free = rqdatac.get_yield_curve(
        start_date="2025-01-02",
        end_date="2025-01-10",
        tenor=RISK_FREE_FIELDS,
        market="cn",
    )
    calls += 1
    rf_frame = risk_free.reset_index().rename(columns={"trading_date": "trade_date", "index": "trade_date"})
    datasets["risk_free_rate"] = _frame_summary(rf_frame, ["trade_date"], RISK_FREE_FIELDS)
    datasets["risk_free_rate"]["unit_conclusion"] = _infer_yield_unit(risk_free)
    datasets["risk_free_rate"]["quality_issues"] = [
        issue.to_dict() for issue in check_risk_free_rate(rf_frame)
    ]

    datasets["pit_cross_validation"] = _pit_cross_validation(rqdatac, "600519.XSHG", "2024q3")
    calls += datasets["pit_cross_validation"].get("actual_calls", 0)

    result = {
        "status": "success",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "symbols": symbols,
        "rqdata_calls": calls,
        "datasets": datasets,
    }
    _write_smoke_report(result, output)
    return result


def _write_smoke_report(result: dict[str, Any], output: Path) -> None:
    (output / "hxz_p0_smoke_validation.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    lines = ["# HXZ P0 Smoke Validation", "", f"status: {result['status']}", ""]
    if result["status"] != "success":
        lines.append(result.get("reason", ""))
    else:
        lines.append(f"rqdata_calls: {result['rqdata_calls']}")
        for dataset, info in result["datasets"].items():
            lines.extend(["", f"## {dataset}", ""])
            if isinstance(info, dict):
                for key, value in info.items():
                    if key in {"head"}:
                        continue
                    lines.append(f"- {key}: {value}")
    (output / "hxz_p0_smoke_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_task(
    *,
    dataset: str,
    root: Path,
    symbols: list[str],
    trading_dates: list[str],
    quarters: list[str],
    start_date: str,
    end_date: str,
    start_quarter: str,
    end_quarter: str,
    symbol_batch_size: int,
    date_chunk_size: int,
    quarter_chunk_size: int,
) -> HXZP0Task:
    symbol_batches = max(1, math.ceil(len(symbols) / symbol_batch_size))
    if dataset == "financial_pit_quarterly":
        chunks = symbol_batches * max(1, math.ceil(len(quarters) / quarter_chunk_size))
        rows = int(len(symbols) * len(quarters) * 1.2)
        target = root / "financial_pit_quarterly"
        return HXZP0Task(
            dataset=dataset,
            source_api="rqdatac.get_pit_financials_ex",
            target_path=str(target),
            requested_fields=["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"] + PIT_FIELDS,
            start_date=None,
            end_date=None,
            start_quarter=start_quarter,
            end_quarter=end_quarter,
            total_symbols=len(symbols),
            symbol_batch_size=symbol_batch_size,
            date_or_quarter_chunk_size=quarter_chunk_size,
            estimated_chunks=chunks,
            estimated_api_calls=chunks,
            estimated_rows=rows,
            rough_disk_size=_rough_size(rows, 9),
            existing_partitions=_existing_partitions(target),
            missing_partitions=_missing_year_partitions(target, range(2016, int(end_date[:4]) + 1)),
            write_mode="dry-run only; future year partition by info_date, append + deduplicate after key validation",
            resume_key="dataset + symbol_batch + quarter_chunk + statements_mode",
            quality_checks=financial_pit_quality_checks(),
            status="planned",
            blocked_reason="formal production write not enabled in this stage",
        )
    if dataset == "financial_factor_daily_pit":
        chunks = symbol_batches * max(1, math.ceil(len(trading_dates) / date_chunk_size))
        rows = len(symbols) * len(trading_dates)
        target = root / "financial_factor_daily_pit"
        years = sorted({int(date[:4]) for date in trading_dates})
        return HXZP0Task(
            dataset=dataset,
            source_api="rqdatac.get_factor",
            target_path=str(target),
            requested_fields=["trade_date", "order_book_id"] + FACTOR_FIELDS,
            start_date=start_date,
            end_date=end_date,
            start_quarter=None,
            end_quarter=None,
            total_symbols=len(symbols),
            symbol_batch_size=symbol_batch_size,
            date_or_quarter_chunk_size=date_chunk_size,
            estimated_chunks=chunks,
            estimated_api_calls=chunks,
            estimated_rows=rows,
            rough_disk_size=_rough_size(rows, len(FACTOR_FIELDS) + 2),
            existing_partitions=_existing_partitions(target),
            missing_partitions=_missing_year_partitions(target, years),
            write_mode="dry-run only; future year partition by trade_date, append + deduplicate",
            resume_key="dataset + symbol_batch + date_chunk",
            quality_checks=financial_factor_quality_checks(),
            status="planned",
            blocked_reason="formal production write not enabled in this stage",
        )
    if dataset == "risk_free_rate":
        rows = len(trading_dates)
        target = root / "risk_free_rate"
        years = sorted({int(date[:4]) for date in trading_dates})
        return HXZP0Task(
            dataset=dataset,
            source_api="rqdatac.get_yield_curve",
            target_path=str(target),
            requested_fields=["trade_date"] + RISK_FREE_FIELDS + ["source", "fetched_at"],
            start_date=start_date,
            end_date=end_date,
            start_quarter=None,
            end_quarter=None,
            total_symbols=0,
            symbol_batch_size=0,
            date_or_quarter_chunk_size=date_chunk_size,
            estimated_chunks=max(1, math.ceil(rows / date_chunk_size)),
            estimated_api_calls=max(1, math.ceil(rows / date_chunk_size)),
            estimated_rows=rows,
            rough_disk_size=_rough_size(rows, len(RISK_FREE_FIELDS) + 3),
            existing_partitions=_existing_partitions(target),
            missing_partitions=_missing_year_partitions(target, years),
            write_mode="dry-run only; future year partition by trade_date, append + deduplicate",
            resume_key="dataset + date_chunk",
            quality_checks=risk_free_quality_checks(),
            status="planned",
            blocked_reason="formal production write not enabled in this stage",
        )
    raise ValueError(f"unsupported dataset: {dataset}")


def _normalize_datasets(datasets: list[str] | str) -> list[str]:
    if datasets == "all":
        return DATASETS
    raw = datasets.split(",") if isinstance(datasets, str) else datasets
    selected = [item.strip() for item in raw if item.strip()]
    unknown = sorted(set(selected) - set(DATASETS))
    if unknown:
        raise ValueError(f"unknown HXZ P0 datasets: {', '.join(unknown)}")
    return selected


def _load_symbols(root: Path) -> list[str]:
    path = root / "instruments" / "instruments.parquet"
    if not path.exists():
        return []
    frame = pd.read_parquet(path)
    if "type" in frame.columns:
        frame = frame[frame["type"].astype(str).eq("CS")]
    if "order_book_id" not in frame.columns:
        return []
    return sorted(frame["order_book_id"].dropna().astype(str).unique().tolist())


def _load_trading_dates(root: Path, start_date: str, end_date: str) -> list[str]:
    path = root / "trading_calendar" / "trading_calendar.parquet"
    if not path.exists():
        return pd.date_range(start_date, end_date, freq="B").strftime("%Y-%m-%d").tolist()
    frame = pd.read_parquet(path)
    dates = pd.to_datetime(frame["trade_date"], errors="coerce")
    mask = (dates >= pd.Timestamp(start_date)) & (dates <= pd.Timestamp(end_date))
    if "is_open" in frame.columns:
        mask = mask & frame["is_open"].fillna(False).astype(bool)
    return dates[mask].dt.strftime("%Y-%m-%d").tolist()


def _latest_data_date(root: Path) -> str | None:
    candidates: list[str] = []
    for dataset in ["prices_1d_none", "valuation_1d", "tradability_1d"]:
        for file in sorted((root / dataset).glob("year=*.parquet")):
            try:
                frame = pd.read_parquet(file, columns=["trade_date"])
            except Exception:
                continue
            if not frame.empty:
                candidates.append(pd.to_datetime(frame["trade_date"]).max().strftime("%Y-%m-%d"))
    return max(candidates) if candidates else None


def _quarters_between(start: str, end: str) -> list[str]:
    sy, sq = int(start[:4]), int(start[-1])
    ey, eq = int(end[:4]), int(end[-1])
    quarters = []
    y, q = sy, sq
    while (y, q) <= (ey, eq):
        quarters.append(f"{y}q{q}")
        q += 1
        if q == 5:
            y += 1
            q = 1
    return quarters


def _quarter_for_date(date_str: str) -> str:
    ts = pd.Timestamp(date_str)
    return f"{ts.year}q{((ts.month - 1) // 3) + 1}"


def _existing_partitions(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(item.name for item in path.glob("year=*.parquet"))


def _missing_year_partitions(path: Path, years) -> list[str]:
    existing = set(_existing_partitions(path))
    return [f"year={year}.parquet" for year in years if f"year={year}.parquet" not in existing]


def _rough_size(rows: int, columns: int) -> str:
    size = rows * columns * 12
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def _checksum(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def financial_pit_quality_checks() -> list[str]:
    return [
        "required columns exist",
        "quarter format matches YYYYq[1-4]",
        "info_date is parseable and not earlier than quarter end without reason",
        "candidate primary keys are unique or version columns are retained",
        "multi-version rows are detected",
        "if_adjusted distribution is recorded",
        "numeric accounting fields are numeric",
        "total_assets is positive where present",
        "equity and profit coverage are reported",
    ]


def financial_factor_quality_checks() -> list[str]:
    return [
        "trade_date + order_book_id unique",
        "required fields exist",
        "primary field coverage is above smoke threshold",
        "dates are ordered per symbol",
        "PIT step-change counts are reported",
        "extreme values are flagged",
        "sample rows reconcile against quarterly PIT values",
        "new quarter values do not appear before info_date",
    ]


def risk_free_quality_checks() -> list[str]:
    return [
        "trade_date unique",
        "tenor fields exist",
        "unit is inferred and recorded",
        "values are in a reasonable rate range",
        "missing dates are reported",
        "term-structure anomalies are warned",
    ]


def _frame_summary(frame: pd.DataFrame, keys: list[str], fields: list[str]) -> dict[str, Any]:
    return {
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "duplicate_keys": int(frame.duplicated(keys).sum()) if set(keys).issubset(frame.columns) else None,
        "null_rates": {
            field: round(float(frame[field].isna().mean()), 6)
            for field in fields
            if field in frame.columns
        },
        "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
        "head": frame.head(5).astype(str).to_dict("records"),
    }


def _pit_version_policy(rqdatac: Any, symbols: list[str]) -> dict[str, Any]:
    try:
        frame = rqdatac.get_pit_financials_ex(
            order_book_ids=symbols[:2],
            fields=PIT_FIELDS,
            start_quarter="2024q3",
            end_quarter="2024q3",
            date="2025-01-10",
            statements="all",
            market="cn",
        ).reset_index()
    except Exception as exc:
        return {
            "status": "failed",
            "actual_calls": 1,
            "error": f"{type(exc).__name__}: {exc}",
            "conclusion": "cannot infer statements=all; do not guess version key",
        }
    keys = ["order_book_id", "quarter"]
    version_rows = int(frame.duplicated(keys, keep=False).sum()) if set(keys).issubset(frame.columns) else 0
    return {
        "status": "success",
        "actual_calls": 1,
        "rows": int(len(frame)),
        "multi_version_rows": version_rows,
        "recommended_raw_key": ["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"],
        "conclusion": "retain version metadata; use latest for as-of snapshots and all for revision audit when available",
    }


def _pit_cross_validation(rqdatac: Any, symbol: str, quarter: str) -> dict[str, Any]:
    try:
        latest = _pit_frame(rqdatac.get_pit_financials_ex(
            order_book_ids=[symbol],
            fields=PIT_FIELDS,
            start_quarter=quarter,
            end_quarter=quarter,
            date="2025-01-10",
            statements="latest",
            market="cn",
        ))
        if latest.empty or "info_date" not in latest.columns:
            return {"status": "empty", "actual_calls": 1, "conclusion": "no PIT row found"}
        info_date = pd.Timestamp(latest["info_date"].iloc[0]).date()
        before = (pd.Timestamp(info_date) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        after = pd.Timestamp(info_date).strftime("%Y-%m-%d")
        before_pit = _pit_frame(rqdatac.get_pit_financials_ex(
            order_book_ids=[symbol],
            fields=PIT_FIELDS,
            start_quarter=quarter,
            end_quarter=quarter,
            date=before,
            statements="latest",
            market="cn",
        ))
        after_pit = _pit_frame(rqdatac.get_pit_financials_ex(
            order_book_ids=[symbol],
            fields=PIT_FIELDS,
            start_quarter=quarter,
            end_quarter=quarter,
            date=after,
            statements="latest",
            market="cn",
        ))
        factor = rqdatac.get_factor(
            [symbol],
            ["total_assets_mrq_0", "net_profit_parent_company_mrq_0"],
            start_date=before,
            end_date=after,
            expect_df=True,
        ).reset_index()
        return {
            "status": "success",
            "actual_calls": 4,
            "symbol": symbol,
            "quarter": quarter,
            "info_date": str(info_date),
            "before_query_date": before,
            "after_query_date": after,
            "before_pit_rows": int(len(before_pit)),
            "after_pit_rows": int(len(after_pit)),
            "factor_rows": int(len(factor)),
            "announcement_before_visible": int(len(before_pit)) > 0,
            "announcement_after_visible": int(len(after_pit)) > 0,
            "conclusion": (
                "announcement visibility validated if before_pit_rows is 0 and after_pit_rows > 0; "
                "if not, inspect non-trading day and revision behavior before production backfill"
            ),
        }
    except Exception as exc:
        return {
            "status": "failed",
            "actual_calls": 1,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _infer_yield_unit(frame: pd.DataFrame) -> str:
    values = pd.to_numeric(frame.stack(), errors="coerce").dropna()
    if values.empty:
        return "unknown"
    median = float(values.median())
    if 0 < median < 0.2:
        return "decimal annual rate"
    if 0.2 <= median < 20:
        return "percent annual rate"
    return "unknown_or_out_of_range"


def _pit_frame(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value.reset_index()
    return pd.DataFrame(value).reset_index()
