from __future__ import annotations

import argparse
import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.hxz_p0_backfill import (
    RISK_FREE_FIELDS,
    append_hxz_status,
    load_hxz_status,
)
from rq_platform.etl.hxz_p0_quality import check_financial_pit_quarterly, check_risk_free_rate
from rq_platform.settings import settings


PIT_FIELDS = ["total_assets", "equity_parent_company", "total_equity", "net_profit_parent_company"]
STATUS_PATH = settings.data_root_path / "update_logs" / "hxz_p0b_formal_backfill_status.csv"
OUTPUT_DIR = Path("reports/data_audit")


def main() -> int:
    parser = argparse.ArgumentParser(description="Formal HXZ P0B backfill for risk-free rate and PIT quarterly financials.")
    parser.add_argument("--dataset", default="all", choices=["all", "risk_free_rate", "financial_pit_quarterly"])
    parser.add_argument("--start-date", default="2016-01-04")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--start-quarter", default="2014q4")
    parser.add_argument("--end-quarter", default=None)
    parser.add_argument("--symbol-batch-size", type=int, default=200)
    parser.add_argument("--quarter-chunk-size", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-hxz-p0b-backfill", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.confirm_hxz_p0b_backfill:
        raise SystemExit("Refusing formal backfill without --confirm-hxz-p0b-backfill or --dry-run.")

    latest_date = args.end_date or latest_local_date()
    end_quarter = args.end_quarter or latest_completed_quarter(latest_date)
    run_id = f"hxz_p0b_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    datasets = ["risk_free_rate", "financial_pit_quarterly"] if args.dataset == "all" else [args.dataset]
    symbols = load_symbols()
    chunks = build_chunks(
        datasets=datasets,
        symbols=symbols,
        start_date=args.start_date,
        end_date=latest_date,
        start_quarter=args.start_quarter,
        end_quarter=end_quarter,
        symbol_batch_size=args.symbol_batch_size,
        quarter_chunk_size=args.quarter_chunk_size,
    )
    plan = {
        "run_id": run_id,
        "mode": "dry_run" if args.dry_run else "formal",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "datasets": datasets,
        "start_date": args.start_date,
        "end_date": latest_date,
        "start_quarter": args.start_quarter,
        "end_quarter": end_quarter,
        "chunk_count": len(chunks),
        "estimated_api_calls": len(chunks),
        "chunks": chunks,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "hxz_p0b_formal_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.dry_run:
        print(f"status=dry_run")
        print(f"chunks={len(chunks)}")
        print(f"estimated_api_calls={len(chunks)}")
        print(f"plan={OUTPUT_DIR / 'hxz_p0b_formal_plan.json'}")
        return 0

    token = os.getenv("RQDATAC_KEY") or settings.rqdata_license
    if not token:
        raise SystemExit("RQDATAC_KEY/RQDATA_LICENSE is not set; no RQData call was made.")
    import rqdatac  # type: ignore

    rqdatac.init(username="license", password=token)
    status = load_hxz_status(STATUS_PATH)
    results = []
    failures = 0
    calls = 0
    for chunk in chunks:
        if chunk_done(status, chunk):
            results.append({**chunk, "status": "skipped_existing", "rows": 0})
            continue
        started = datetime.now().isoformat(timespec="seconds")
        try:
            if chunk["dataset"] == "risk_free_rate":
                frame = fetch_risk_free(rqdatac, chunk)
                calls += 1
                if frame.empty:
                    result = write_status(run_id, chunk, "empty", started, 1, 0, "")
                else:
                    issues = check_risk_free_rate(frame)
                    if any(issue.severity == "error" for issue in issues):
                        raise ValueError(f"risk_free_rate quality errors: {[i.to_dict() for i in issues]}")
                    paths = write_year_partitions(frame, "risk_free_rate", ["trade_date"])
                    result = write_status(run_id, chunk, "succeeded", started, 1, len(frame), ";".join(map(str, paths)))
            else:
                frame = fetch_pit_quarterly(rqdatac, chunk)
                calls += 1
                if frame.empty:
                    result = write_status(run_id, chunk, "empty", started, 1, 0, "")
                else:
                    ensure_pit_key_is_lossless(frame)
                    issues = check_financial_pit_quarterly(frame)
                    if any(issue.severity == "error" for issue in issues):
                        raise ValueError(f"financial_pit_quarterly quality errors: {[i.to_dict() for i in issues]}")
                    paths = write_year_partitions(frame, "financial_pit_quarterly", ["order_book_id", "quarter", "info_date"])
                    result = write_status(run_id, chunk, "succeeded", started, 1, len(frame), ";".join(map(str, paths)))
            results.append(result)
        except Exception as exc:
            failures += 1
            result = write_status(
                run_id,
                chunk,
                classify_error(exc),
                started,
                1,
                0,
                "",
                type(exc).__name__,
                sanitize_error(exc),
            )
            results.append(result)
            if classify_error(exc) in {"auth_failed", "quota_stopped"} or failures >= failure_limit(chunk["dataset"]):
                break
    report = build_report(results, calls, latest_date, args.start_quarter, end_quarter)
    write_reports(report)
    print(f"status={report['status']}")
    print(f"rqdata_calls={calls}")
    print(f"succeeded_chunks={report['succeeded_chunks']}")
    print(f"failed_chunks={report['failed_chunks']}")
    print(f"empty_chunks={report['empty_chunks']}")
    print(f"markdown={OUTPUT_DIR / 'hxz_p0b_formal_backfill.md'}")
    return 0 if report["status"] == "success" else 1


def build_chunks(*, datasets, symbols, start_date, end_date, start_quarter, end_quarter, symbol_batch_size, quarter_chunk_size):
    chunks = []
    if "risk_free_rate" in datasets:
        years = list(range(int(start_date[:4]), int(end_date[:4]) + 1))
        for year in years:
            chunks.append(
                {
                    "dataset": "risk_free_rate",
                    "chunk_id": f"risk_free_rate:{year}",
                    "start_date": max(start_date, f"{year}-01-01"),
                    "end_date": min(end_date, f"{year}-12-31"),
                    "range_start": max(start_date, f"{year}-01-01"),
                    "range_end": min(end_date, f"{year}-12-31"),
                    "symbols": [],
                }
            )
    if "financial_pit_quarterly" in datasets:
        quarters = quarters_between(start_quarter, end_quarter)
        for sidx in range(0, len(symbols), symbol_batch_size):
            batch = symbols[sidx : sidx + symbol_batch_size]
            for qidx in range(0, len(quarters), quarter_chunk_size):
                qchunk = quarters[qidx : qidx + quarter_chunk_size]
                chunks.append(
                    {
                        "dataset": "financial_pit_quarterly",
                        "chunk_id": f"financial_pit_quarterly:s{sidx // symbol_batch_size:03d}:q{qidx // quarter_chunk_size:03d}",
                        "start_quarter": qchunk[0],
                        "end_quarter": qchunk[-1],
                        "range_start": qchunk[0],
                        "range_end": qchunk[-1],
                        "symbol_start": batch[0],
                        "symbol_end": batch[-1],
                        "symbols": batch,
                    }
                )
    return chunks


def fetch_risk_free(rqdatac, chunk):
    frame = rqdatac.get_yield_curve(chunk["start_date"], chunk["end_date"], tenor=RISK_FREE_FIELDS, market="cn")
    if frame is None:
        return pd.DataFrame()
    output = frame.reset_index().rename(columns={"trading_date": "trade_date", "index": "trade_date"})
    output["trade_date"] = pd.to_datetime(output["trade_date"]).dt.strftime("%Y-%m-%d")
    output["source"] = "rqdatac.get_yield_curve"
    output["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return output[["trade_date"] + RISK_FREE_FIELDS + ["source", "fetched_at"]]


def fetch_pit_quarterly(rqdatac, chunk):
    frame = rqdatac.get_pit_financials_ex(
        order_book_ids=chunk["symbols"],
        fields=PIT_FIELDS,
        start_quarter=chunk["start_quarter"],
        end_quarter=chunk["end_quarter"],
        date=latest_local_date(),
        statements="all",
        market="cn",
    )
    if frame is None:
        return pd.DataFrame()
    output = frame.reset_index()
    output["info_date"] = pd.to_datetime(output["info_date"]).dt.strftime("%Y-%m-%d")
    output["rice_create_tm"] = pd.to_datetime(output["rice_create_tm"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    output["source"] = "rqdatac.get_pit_financials_ex"
    output["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return output[
        [
            "order_book_id",
            "quarter",
            "info_date",
            "rice_create_tm",
            "if_adjusted",
            *PIT_FIELDS,
            "source",
            "fetched_at",
        ]
    ]


def write_year_partitions(frame: pd.DataFrame, dataset: str, keys: list[str]) -> list[Path]:
    root = settings.data_root_path / dataset
    root.mkdir(parents=True, exist_ok=True)
    output_paths = []
    date_col = "trade_date" if "trade_date" in frame.columns else "info_date"
    work = frame.copy()
    work["_year"] = pd.to_datetime(work[date_col]).dt.year
    for year, group in work.groupby("_year"):
        path = root / f"year={int(year)}.parquet"
        existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
        merged = pd.concat([existing, group.drop(columns=["_year"])], ignore_index=True)
        if merged.duplicated(keys).any():
            dupes = merged[merged.duplicated(keys, keep=False)].head(20)
            raise ValueError(f"duplicate primary key for {dataset}: {dupes[keys].to_dict('records')}")
        merged = merged.sort_values(keys).reset_index(drop=True)
        tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        merged.to_parquet(tmp, index=False)
        verify = pd.read_parquet(tmp)
        if len(verify) != len(merged):
            tmp.unlink(missing_ok=True)
            raise ValueError(f"atomic write verification failed for {path}")
        tmp.replace(path)
        output_paths.append(path)
    return output_paths


def ensure_pit_key_is_lossless(frame: pd.DataFrame) -> None:
    keys = ["order_book_id", "quarter", "info_date"]
    if frame.duplicated(keys).any():
        dupes = frame[frame.duplicated(keys, keep=False)].head(20)
        raise ValueError(f"financial_pit_quarterly key conflict: {dupes[keys + ['rice_create_tm', 'if_adjusted']].to_dict('records')}")


def write_status(run_id, chunk, status, started, calls, rows, output, error_type="", error_message=""):
    finished = datetime.now().isoformat(timespec="seconds")
    record = {
        "run_id": run_id,
        "dataset": chunk["dataset"],
        "mode": "formal",
        "chunk_id": chunk["chunk_id"],
        "symbol_start": chunk.get("symbol_start", ""),
        "symbol_end": chunk.get("symbol_end", ""),
        "symbol_count": len(chunk.get("symbols", [])),
        "range_start": chunk["range_start"],
        "range_end": chunk["range_end"],
        "planned_calls": 1,
        "actual_calls": calls,
        "returned_rows": rows,
        "status": status,
        "started_at": started,
        "finished_at": finished,
        "error_type": error_type,
        "error_message_sanitized": error_message,
        "retryable": status == "failed",
        "output_path": output,
        "checksum": hashlib.sha256(f"{chunk['chunk_id']}:{rows}:{status}".encode()).hexdigest(),
    }
    append_hxz_status(STATUS_PATH, record)
    return record


def chunk_done(status: pd.DataFrame, chunk: dict[str, Any]) -> bool:
    if status.empty or "chunk_id" not in status.columns:
        return False
    matched = status[
        status["chunk_id"].astype(str).eq(chunk["chunk_id"])
        & status["dataset"].astype(str).eq(chunk["dataset"])
        & status["status"].astype(str).isin(["succeeded", "empty"])
    ]
    return not matched.empty


def build_report(results, calls, latest_date, start_quarter, end_quarter):
    status_counts = pd.Series([r["status"] for r in results]).value_counts().to_dict() if results else {}
    report = {
        "status": "success" if not any(r["status"] in {"failed", "quota_stopped", "auth_failed"} for r in results) else "failed",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "rqdata_calls": calls,
        "latest_date": latest_date,
        "start_quarter": start_quarter,
        "end_quarter": end_quarter,
        "succeeded_chunks": int(status_counts.get("succeeded", 0)),
        "failed_chunks": int(status_counts.get("failed", 0) + status_counts.get("quota_stopped", 0) + status_counts.get("auth_failed", 0)),
        "empty_chunks": int(status_counts.get("empty", 0)),
        "skipped_chunks": int(status_counts.get("skipped_existing", 0)),
        "datasets": summarize_written_datasets(),
    }
    return report


def summarize_written_datasets():
    return {
        "risk_free_rate": summarize_dataset("risk_free_rate", "trade_date"),
        "financial_pit_quarterly": summarize_dataset("financial_pit_quarterly", "info_date"),
    }


def summarize_dataset(dataset: str, date_col: str):
    root = settings.data_root_path / dataset
    files = sorted(root.glob("year=*.parquet"))
    frames = [pd.read_parquet(path) for path in files]
    if not frames:
        return {"rows": 0, "files": [], "path": str(root)}
    frame = pd.concat(frames, ignore_index=True)
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    result = {
        "path": str(root),
        "files": [str(path) for path in files],
        "rows": int(len(frame)),
        "min_date": dates.min().strftime("%Y-%m-%d") if dates.notna().any() else None,
        "max_date": dates.max().strftime("%Y-%m-%d") if dates.notna().any() else None,
        "disk_bytes": sum(path.stat().st_size for path in files),
        "checksum": checksum_files(files),
    }
    if "order_book_id" in frame.columns:
        result["symbols"] = int(frame["order_book_id"].nunique())
    if "quarter" in frame.columns:
        result["quarters"] = int(frame["quarter"].nunique())
        result["multi_version_stock_quarters"] = int((frame.groupby(["order_book_id", "quarter"]).size() > 1).sum())
        result["if_adjusted_distribution"] = {str(k): int(v) for k, v in frame["if_adjusted"].value_counts(dropna=False).items()}
        result["null_rates"] = {field: round(float(frame[field].isna().mean()), 6) for field in PIT_FIELDS if field in frame.columns}
    else:
        result["null_rates"] = {field: round(float(frame[field].isna().mean()), 6) for field in RISK_FREE_FIELDS if field in frame.columns}
    return result


def write_reports(report):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "hxz_p0b_formal_backfill.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    lines = [
        "# HXZ P0B Formal Backfill",
        "",
        f"status: {report['status']}",
        f"rqdata_calls: {report['rqdata_calls']}",
        f"succeeded_chunks: {report['succeeded_chunks']}",
        f"failed_chunks: {report['failed_chunks']}",
        f"empty_chunks: {report['empty_chunks']}",
        f"skipped_chunks: {report['skipped_chunks']}",
        "",
        "## Datasets",
    ]
    for dataset, info in report["datasets"].items():
        lines.append(f"### {dataset}")
        for key, value in info.items():
            if key != "files":
                lines.append(f"- {key}: {value}")
        lines.append("")
    lines.append("No financial_factor_daily_pit full backfill was executed.")
    (OUTPUT_DIR / "hxz_p0b_formal_backfill.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUTPUT_DIR / "hxz_p0b_reconciliation.md").write_text(render_reconciliation(report), encoding="utf-8")
    update_plan(report)


def render_reconciliation(report):
    lines = ["# HXZ P0B Reconciliation", ""]
    for dataset, info in report["datasets"].items():
        lines.append(f"- {dataset}: rows={info.get('rows')}, range={info.get('min_date')} to {info.get('max_date')}, path={info.get('path')}")
    return "\n".join(lines) + "\n"


def update_plan(report):
    path = OUTPUT_DIR / "hxz_backfill_plan.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data["p0b_formal_backfill"] = {
        "status": report["status"],
        "rqdata_calls": report["rqdata_calls"],
        "datasets": report["datasets"],
        "financial_factor_daily_pit_full_backfill": False,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def latest_local_date():
    root = settings.data_root_path / "trading_calendar" / "trading_calendar.parquet"
    frame = pd.read_parquet(root)
    return pd.to_datetime(frame["trade_date"]).max().strftime("%Y-%m-%d")


def latest_completed_quarter(date_str):
    ts = pd.Timestamp(date_str)
    q = (ts.month - 1) // 3
    year = ts.year
    if q == 0:
        year -= 1
        q = 4
    return f"{year}q{q}"


def load_symbols():
    frame = pd.read_parquet(settings.data_root_path / "instruments" / "instruments.parquet")
    frame = frame[frame["type"].astype(str).eq("CS")]
    return sorted(frame["order_book_id"].dropna().astype(str).unique().tolist())


def quarters_between(start, end):
    y, q = int(start[:4]), int(start[-1])
    ey, eq = int(end[:4]), int(end[-1])
    out = []
    while (y, q) <= (ey, eq):
        out.append(f"{y}q{q}")
        q += 1
        if q == 5:
            y += 1
            q = 1
    return out


def checksum_files(files):
    h = hashlib.sha256()
    for path in files:
        h.update(path.name.encode())
        h.update(str(path.stat().st_size).encode())
    return h.hexdigest()


def classify_error(exc):
    text = str(exc).lower()
    if "quota" in text:
        return "quota_stopped"
    if "auth" in text or "permission" in text or "license" in text:
        return "auth_failed"
    return "failed"


def sanitize_error(exc):
    return str(exc).replace(settings.rqdata_license or "", "<redacted>")


def failure_limit(dataset):
    return 5 if dataset == "risk_free_rate" else 30


if __name__ == "__main__":
    raise SystemExit(main())
