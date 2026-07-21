from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.financial_pit_field_pack_plan import (
    FinancialPitField,
    FinancialPitFieldPackTask,
)
from rq_platform.settings import settings


DATASET_NAME = "financial_pit_field_pack"
STATUS_PATH = settings.data_root_path / "update_logs" / "financial_pit_field_pack_status.csv"
KEY_COLUMNS = ["order_book_id", "report_period", "info_date"]


def run_financial_pit_field_pack_backfill(
    task: FinancialPitFieldPackTask,
    *,
    confirm: bool = False,
) -> dict[str, Any]:
    run_id = f"financial_pit_field_pack_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    plan = _task_plan(run_id, task)
    if task.dry_run:
        return {**plan, "status": "dry_run", "results": []}
    if not confirm:
        raise RuntimeError("Refusing financial PIT field pack backfill without --confirm-financial-pit-field-pack-backfill.")

    rqdatac = _init_rqdatac()
    results = []
    total_rows = 0
    failures = 0
    for batch_id, symbols in enumerate(_chunks(task.symbols, task.batch_size), start=1):
        started = datetime.now().isoformat(timespec="seconds")
        try:
            frame = fetch_financial_pit_field_pack(rqdatac, symbols, task.fields, task.start_quarter, task.end_quarter)
            if frame.empty:
                result = _status_row(run_id, task, batch_id, symbols, 0, "empty", "", "")
            else:
                paths = write_financial_pit_field_pack(frame, overwrite=task.overwrite and batch_id == 1)
                total_rows += len(frame)
                result = _status_row(run_id, task, batch_id, symbols, len(frame), "success", ";".join(str(path) for path in paths), "")
            result["started_at"] = started
            append_status(result)
            results.append(result)
        except Exception as exc:
            failures += 1
            result = _status_row(run_id, task, batch_id, symbols, 0, "failed", "", _sanitize_error(exc))
            result["started_at"] = started
            append_status(result)
            results.append(result)
            if _is_auth_or_quota_error(exc) or failures >= 5:
                break
    status = "success" if failures == 0 else "failed"
    return {**plan, "status": status, "total_rows": total_rows, "failed_batches": failures, "results": results}


def fetch_financial_pit_field_pack(
    rqdatac: Any,
    symbols: list[str],
    fields: list[FinancialPitField],
    start_quarter: str,
    end_quarter: str,
) -> pd.DataFrame:
    rq_fields = [field.rqdata_field for field in fields]
    raw = rqdatac.get_pit_financials_ex(
        order_book_ids=symbols,
        fields=rq_fields,
        start_quarter=start_quarter,
        end_quarter=end_quarter,
        date=datetime.now().date().isoformat(),
        statements="all",
        market="cn",
    )
    if raw is None:
        return pd.DataFrame()
    return normalize_financial_pit_field_pack(raw, fields)


def normalize_financial_pit_field_pack(raw: pd.DataFrame, fields: list[FinancialPitField]) -> pd.DataFrame:
    frame = pd.DataFrame(raw).reset_index()
    rename_map = {
        "quarter": "report_period",
        "report_quarter": "report_period",
        "pub_date": "info_date",
        "announcement_date": "info_date",
        "publish_date": "info_date",
    }
    frame = frame.rename(columns={key: value for key, value in rename_map.items() if key in frame.columns})
    if "report_period" not in frame.columns and "report_date" in frame.columns:
        frame["report_period"] = pd.to_datetime(frame["report_date"], errors="coerce").dt.to_period("Q").astype(str).str.lower().str.replace("q", "q", regex=False)
    if "quarter" not in frame.columns and "report_period" in frame.columns:
        frame["quarter"] = frame["report_period"]
    if "report_period" not in frame.columns and "quarter" in frame.columns:
        frame["report_period"] = frame["quarter"]
    if "info_date" in frame.columns:
        frame["info_date"] = pd.to_datetime(frame["info_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if "rice_create_tm" in frame.columns:
        frame["rice_create_tm"] = pd.to_datetime(frame["rice_create_tm"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    if "if_adjusted" not in frame.columns:
        frame["if_adjusted"] = pd.NA
    if "statement_type" not in frame.columns:
        frame["statement_type"] = pd.NA
    frame["source"] = "rqdatac.get_pit_financials_ex"
    frame["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    mapping = {field.canonical_field: field.rqdata_field for field in fields}
    frame["field_mapping_json"] = json.dumps(mapping, ensure_ascii=False, sort_keys=True)
    required = [
        "order_book_id",
        "report_period",
        "quarter",
        "info_date",
        "rice_create_tm",
        "if_adjusted",
        "statement_type",
    ]
    for column in required:
        if column not in frame.columns:
            frame[column] = pd.NA
    field_columns = [field.rqdata_field for field in fields if field.rqdata_field in frame.columns]
    out = frame[required + field_columns + ["field_mapping_json", "source", "fetched_at"]].copy()
    out["order_book_id"] = out["order_book_id"].astype(str)
    out["report_period"] = out["report_period"].astype(str)
    return out.sort_values(["order_book_id", "report_period", "info_date"]).reset_index(drop=True)


def write_financial_pit_field_pack(frame: pd.DataFrame, *, overwrite: bool = False) -> list[Path]:
    root = settings.data_root_path / DATASET_NAME
    root.mkdir(parents=True, exist_ok=True)
    work = frame.copy()
    work["_year"] = pd.to_datetime(work["info_date"], errors="coerce").dt.year
    paths = []
    for year, group in work.dropna(subset=["_year"]).groupby("_year"):
        year_dir = root / f"year={int(year)}"
        year_dir.mkdir(parents=True, exist_ok=True)
        path = year_dir / "financial_pit_field_pack.parquet"
        output = group.drop(columns=["_year"]).copy()
        if path.exists() and not overwrite:
            existing = pd.read_parquet(path)
            output = pd.concat([existing, output], ignore_index=True)
        output = output.drop_duplicates(KEY_COLUMNS, keep="last")
        output = output.sort_values(KEY_COLUMNS).reset_index(drop=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        output.to_parquet(tmp, index=False)
        verify = pd.read_parquet(tmp)
        if len(verify) != len(output):
            tmp.unlink(missing_ok=True)
            raise ValueError(f"atomic write verification failed for {path}")
        tmp.replace(path)
        paths.append(path)
    return paths


def append_status(row: dict[str, Any], path: Path = STATUS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    if path.exists():
        existing = pd.read_csv(path)
        frame = pd.concat([existing, frame], ignore_index=True)
    frame.to_csv(path, index=False)


def _init_rqdatac() -> Any:
    token = os.environ.get("RQDATAC_KEY") or settings.rqdata_license
    if not token:
        raise RuntimeError("RQData credential is not configured for this shell.")
    import rqdatac  # type: ignore

    rqdatac.init(username="license", password=token)
    return rqdatac


def _task_plan(run_id: str, task: FinancialPitFieldPackTask) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "start_date": task.start_date,
        "end_date": task.end_date,
        "start_quarter": task.start_quarter,
        "end_quarter": task.end_quarter,
        "symbol_count": len(task.symbols),
        "fields": [asdict(field) for field in task.fields],
        "field_count": len(task.fields),
        "batch_size": task.batch_size,
        "expected_api_calls": task.expected_api_calls,
        "overwrite": task.overwrite,
    }


def _status_row(
    run_id: str,
    task: FinancialPitFieldPackTask,
    batch_id: int,
    symbols: list[str],
    row_count: int,
    status: str,
    output_file: str,
    error: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "dataset": DATASET_NAME,
        "start_date": task.start_date,
        "end_date": task.end_date,
        "year": f"{task.start_quarter}-{task.end_quarter}",
        "batch_id": batch_id,
        "symbol_count": len(symbols),
        "fields": ",".join(field.canonical_field for field in task.fields),
        "row_count": row_count,
        "status": status,
        "error": error,
        "output_file": output_file,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def _sanitize_error(exc: Exception) -> str:
    text = f"{type(exc).__name__}: {exc}"
    for secret in [settings.rqdata_license or "", os.environ.get("RQDATAC_KEY") or ""]:
        if secret:
            text = text.replace(secret, "<redacted>")
    return text[:500]


def _is_auth_or_quota_error(exc: Exception) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(token in text for token in ("permission", "unauthorized", "quota", "license", "auth", "login machine"))
