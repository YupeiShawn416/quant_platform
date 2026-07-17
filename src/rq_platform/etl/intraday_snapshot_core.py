from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file
from rq_platform.etl.intraday_snapshot_plan import (
    DEFAULT_SNAPSHOT_TIMES,
    STATUS_COLUMNS,
    STATUS_PATH,
    IntradaySnapshotPlan,
    IntradaySnapshotTask,
    build_intraday_snapshot_plan,
)
from rq_platform.etl.intraday_snapshot_quality import check_intraday_snapshot_quality
from rq_platform.etl.intraday_snapshot_report import write_intraday_snapshot_quality_report
from rq_platform.settings import settings


DATASET = "intraday_snapshots"
RQDataSource = None


@dataclass
class IntradaySnapshotResult:
    run_id: str
    dataset: str
    start_date: str
    end_date: str
    year: int
    month: int
    snapshot_time: str
    batch_id: str
    symbol_count: int
    row_count: int
    status: str
    error: str = ""
    output_file: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset": self.dataset,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "year": self.year,
            "month": self.month,
            "snapshot_time": self.snapshot_time,
            "batch_id": self.batch_id,
            "symbol_count": self.symbol_count,
            "row_count": self.row_count,
            "status": self.status,
            "error": self.error,
            "output_file": self.output_file,
        }


def require_intraday_snapshot_confirmation(*, dry_run: bool, confirm: bool) -> None:
    if dry_run:
        return
    if not confirm:
        raise ValueError("intraday snapshot backfill requires --confirm-intraday-snapshot-backfill")


def run_intraday_snapshot_backfill(
    *,
    start_date: str,
    end_date: str,
    snapshot_times: str | list[str] | None = None,
    batch_size: int = 300,
    dry_run: bool = True,
    overwrite: bool = False,
    confirm_intraday_snapshot_backfill: bool = False,
    source: Any | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    require_intraday_snapshot_confirmation(dry_run=dry_run, confirm=confirm_intraday_snapshot_backfill)
    plan = build_intraday_snapshot_plan(
        start_date=start_date,
        end_date=end_date,
        snapshot_times=snapshot_times,
        overwrite=overwrite,
        dry_run=dry_run,
    )
    if dry_run:
        return {"run_id": run_id or "", "plan": plan, "results": [], "quality_issues": [], "report": {}}

    symbols = _load_snapshot_symbols()
    data_source = source or _new_rqdata_source()
    effective_run_id = run_id or f"intraday_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    results: list[IntradaySnapshotResult] = []
    for task in plan.tasks:
        if task.should_skip:
            for snapshot_time in plan.snapshot_times:
                result = IntradaySnapshotResult(
                    effective_run_id,
                    DATASET,
                    task.start_date,
                    task.end_date,
                    task.year,
                    task.month,
                    snapshot_time,
                    "skip",
                    len(symbols),
                    0,
                    "skipped",
                    task.reason,
                    task.output_path,
                )
                results.append(result)
                _append_status(result)
            continue
        for batch_id, batch in enumerate(_batches(symbols, batch_size), start=1):
            try:
                frame = _fetch_intraday_snapshots(
                    data_source,
                    batch,
                    task.start_date,
                    task.end_date,
                    plan.snapshot_times,
                )
                output_path = merge_intraday_snapshot_partition(
                    frame,
                    Path(task.output_path),
                    overwrite=overwrite and batch_id == 1,
                )
                rows_by_time = frame.groupby("snapshot_time").size().to_dict() if not frame.empty else {}
                for snapshot_time in plan.snapshot_times:
                    row_count = int(rows_by_time.get(snapshot_time, 0))
                    result = IntradaySnapshotResult(
                        effective_run_id,
                        DATASET,
                        task.start_date,
                        task.end_date,
                        task.year,
                        task.month,
                        snapshot_time,
                        str(batch_id),
                        len(batch),
                        row_count,
                        "success" if row_count > 0 else "failed",
                        "" if row_count > 0 else "zero rows returned for snapshot_time",
                        str(output_path),
                    )
                    results.append(result)
                    _append_status(result)
            except Exception as exc:
                for snapshot_time in plan.snapshot_times:
                    result = IntradaySnapshotResult(
                        effective_run_id,
                        DATASET,
                        task.start_date,
                        task.end_date,
                        task.year,
                        task.month,
                        snapshot_time,
                        str(batch_id),
                        len(batch),
                        0,
                        "failed",
                        f"{type(exc).__name__}: {exc}",
                        task.output_path,
                    )
                    results.append(result)
                    _append_status(result)
    quality_issues = check_intraday_snapshot_quality()
    report = write_intraday_snapshot_quality_report(quality_issues=quality_issues)
    return {"run_id": effective_run_id, "plan": plan, "results": results, "quality_issues": quality_issues, "report": report}


def merge_intraday_snapshot_partition(frame: pd.DataFrame, path: Path, *, overwrite: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = _normalize_intraday_snapshot_frame(frame, DEFAULT_SNAPSHOT_TIMES)
    if path.exists() and not overwrite:
        existing = pd.read_parquet(path)
        output = pd.concat([existing, output], ignore_index=True)
    if output.empty:
        if not path.exists():
            output.to_parquet(path, index=False)
        return path
    output = _normalize_intraday_snapshot_frame(output, DEFAULT_SNAPSHOT_TIMES)
    output = output.drop_duplicates(["trade_date", "snapshot_time", "order_book_id"], keep="last")
    output = output.sort_values(["trade_date", "snapshot_time", "order_book_id"]).reset_index(drop=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    output.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)
    return path


def _fetch_intraday_snapshots(
    source: Any,
    order_book_ids: list[str],
    start_date: str,
    end_date: str,
    snapshot_times: list[str],
) -> pd.DataFrame:
    if hasattr(source, "get_intraday_snapshots"):
        raw = source.get_intraday_snapshots(order_book_ids, start_date, end_date, snapshot_times)
    else:
        raw = _get_rqdata_intraday_snapshots(order_book_ids, start_date, end_date)
    return _normalize_intraday_snapshot_frame(raw, snapshot_times)


def _normalize_intraday_snapshot_frame(frame: pd.DataFrame, snapshot_times: list[str]) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=["trade_date", "datetime", "snapshot_time", "order_book_id", "close", "volume", "total_turnover"])
    output = frame.copy()
    if isinstance(output.index, pd.MultiIndex):
        output = output.reset_index()
    elif output.index.name:
        output = output.reset_index()
    rename = {"date": "datetime", "time": "datetime", "order_book_id": "order_book_id"}
    output = output.rename(columns={key: value for key, value in rename.items() if key in output.columns})
    if "datetime" not in output.columns:
        datetime_col = next((column for column in ["datetime", "date", "trading_datetime"] if column in output.columns), None)
        if datetime_col:
            output = output.rename(columns={datetime_col: "datetime"})
    if "order_book_id" not in output.columns:
        id_col = next((column for column in ["order_book_id", "id", "instrument"] if column in output.columns), None)
        if id_col:
            output = output.rename(columns={id_col: "order_book_id"})
    output["datetime"] = pd.to_datetime(output["datetime"], errors="coerce")
    output["trade_date"] = output["datetime"].dt.strftime("%Y-%m-%d")
    output["snapshot_time"] = output["datetime"].dt.strftime("%H:%M")
    output["order_book_id"] = output["order_book_id"].astype(str)
    output = output[output["snapshot_time"].isin(snapshot_times)]
    for column in ["close", "volume", "total_turnover"]:
        if column not in output.columns:
            output[column] = pd.NA
    columns = ["trade_date", "datetime", "snapshot_time", "order_book_id", "close", "volume", "total_turnover"]
    output = output[columns].dropna(subset=["trade_date", "datetime", "snapshot_time", "order_book_id"])
    return output.sort_values(["trade_date", "snapshot_time", "order_book_id"]).reset_index(drop=True)


def _get_rqdata_intraday_snapshots(order_book_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    from rq_platform.data_sources.rqdata_source import RQDataSource as RuntimeRQDataSource

    source = RuntimeRQDataSource()
    source.init()
    import rqdatac

    return rqdatac.get_price(
        list(order_book_ids),
        start_date=start_date,
        end_date=end_date,
        frequency="1m",
        fields=["close", "volume", "total_turnover"],
        adjust_type="none",
        expect_df=True,
    )


def _load_snapshot_symbols() -> list[str]:
    frame = read_single_file("instruments", "instruments.parquet").copy()
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame = frame[frame["order_book_id"].str.endswith((".XSHG", ".XSHE"), na=False)]
    if "board_type" in frame.columns:
        allowed = {"MainBoard", "GEM", "KSH"}
        frame = frame[frame["board_type"].isin(allowed) | frame["board_type"].isna()]
    return sorted(frame["order_book_id"].dropna().drop_duplicates().tolist())


def _batches(items: list[str], batch_size: int) -> list[list[str]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


def _new_rqdata_source() -> Any:
    if RQDataSource is not None:
        return RQDataSource()
    from rq_platform.data_sources.rqdata_source import RQDataSource as RuntimeRQDataSource

    return RuntimeRQDataSource()


def _append_status(result: IntradaySnapshotResult) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = result.to_dict()
    row["created_at"] = datetime.now().isoformat(timespec="seconds")
    frame = pd.DataFrame([row], columns=STATUS_COLUMNS)
    frame.to_csv(STATUS_PATH, mode="a", header=not STATUS_PATH.exists(), index=False)
