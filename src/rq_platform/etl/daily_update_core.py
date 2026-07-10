from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file, write_single_file
from rq_platform.data_sources.rqdata_source import (
    DEFAULT_INDUSTRY_SOURCE,
    RQDataSource,
    VALUATION_COLUMNS,
)
from rq_platform.etl.backfill_core import merge_trading_calendar_file
from rq_platform.etl.daily_update_plan import (
    DailyUpdatePlan,
    DailyUpdateTask,
    build_daily_update_plan,
)
from rq_platform.etl.data_quality_checks import run_data_quality_checks
from rq_platform.etl.daily_update_report import write_daily_update_report
from rq_platform.etl.update_index_membership import DEFAULT_INDEX_IDS as MEMBERSHIP_INDEX_IDS
from rq_platform.etl.update_index_prices import DEFAULT_INDEX_IDS
from rq_platform.etl.update_tradability import update_tradability_dataset
from rq_platform.settings import settings


STATUS_PATH = settings.data_root_path / "update_logs" / "daily_update_status.csv"
STATUS_COLUMNS = [
    "run_id",
    "created_at",
    "dataset",
    "start_date",
    "end_date",
    "year",
    "status",
    "row_count",
    "output_files",
    "error",
]


@dataclass
class DailyUpdateResult:
    run_id: str
    dataset: str
    start_date: str
    end_date: str
    year: int | None
    status: str
    row_count: int = 0
    output_files: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "dataset": self.dataset,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "year": self.year,
            "status": self.status,
            "row_count": self.row_count,
            "output_files": self.output_files,
            "error": self.error,
        }


def require_daily_update_confirmation(*, dry_run: bool, confirm_daily_update: bool) -> None:
    if dry_run:
        return
    if not confirm_daily_update:
        raise ValueError("daily update requires --confirm-daily-update")


def run_daily_update(
    *,
    end_date: str,
    start_date: str | None = None,
    datasets: list[str] | str | None = None,
    force: bool = False,
    dry_run: bool = False,
    confirm_daily_update: bool = False,
    batch_size: int = 300,
    source: RQDataSource | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    require_daily_update_confirmation(dry_run=dry_run, confirm_daily_update=confirm_daily_update)
    plan = build_daily_update_plan(
        start_date=start_date,
        end_date=end_date,
        datasets=datasets,
        force=force,
    )
    if dry_run:
        return {
            "run_id": run_id or "",
            "plan": plan,
            "results": [],
            "quality_issues": [],
            "report": {},
        }

    effective_run_id = run_id or f"daily_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
    if plan.no_op:
        results = [
            DailyUpdateResult(effective_run_id, task.dataset, task.start_date, task.end_date, task.year, "skipped", error="no-op")
            for task in plan.tasks
        ]
        for result in results:
            _append_daily_status(result)
        issues = run_data_quality_checks()
        report = write_daily_update_report(plan=plan, results=results, quality_issues=issues)
        return {"run_id": effective_run_id, "plan": plan, "results": results, "quality_issues": issues, "report": report}

    data_source = source or RQDataSource()
    results: list[DailyUpdateResult] = []
    for task in plan.tasks:
        if task.should_skip:
            result = DailyUpdateResult(
                effective_run_id,
                task.dataset,
                task.start_date,
                task.end_date,
                task.year,
                "skipped",
                error=task.reason,
            )
        else:
            try:
                result = _run_task(effective_run_id, task, data_source, batch_size=batch_size)
            except Exception as exc:
                result = DailyUpdateResult(
                    effective_run_id,
                    task.dataset,
                    task.start_date,
                    task.end_date,
                    task.year,
                    "failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
        results.append(result)
        _append_daily_status(result)

    issues = run_data_quality_checks()
    report = write_daily_update_report(plan=plan, results=results, quality_issues=issues)
    return {"run_id": effective_run_id, "plan": plan, "results": results, "quality_issues": issues, "report": report}


def _run_task(
    run_id: str,
    task: DailyUpdateTask,
    source: RQDataSource,
    *,
    batch_size: int,
) -> DailyUpdateResult:
    if task.dataset == "calendar":
        frame = source.get_trading_calendar(task.start_date, task.end_date)
        path = merge_trading_calendar_file(frame, Path(task.output_path), force=task.action == "rebuild")
        rows = len(pd.read_parquet(path, columns=["trade_date"]))
        return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", rows, str(path))
    if task.dataset == "instruments":
        frame = source.get_instruments()
        path = write_single_file(frame, "instruments", "instruments.parquet")
        return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", len(frame), str(path))
    if task.dataset == "index_prices":
        frame = source.get_index_prices(DEFAULT_INDEX_IDS, task.start_date, task.end_date)
        path = merge_partition_file(
            frame,
            Path(task.output_path),
            dedupe_keys=["trade_date", "order_book_id"],
        )
        return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", len(frame), str(path))
    if task.dataset == "prices":
        return _update_prices(run_id, task, source, batch_size=batch_size)
    if task.dataset == "tradability":
        result = update_tradability_dataset(year=int(task.year), adjust_type="pre")
        return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", result["rows"], result["path"])
    if task.dataset == "valuation":
        return _update_valuation(run_id, task, source, batch_size=batch_size)
    if task.dataset == "industry":
        return _update_industry(run_id, task, source)
    if task.dataset == "index_members":
        return _update_index_members(run_id, task, source)
    raise ValueError(f"unsupported dataset: {task.dataset}")


def merge_partition_file(df: pd.DataFrame, path: Path, *, dedupe_keys: list[str]) -> Path:
    if df.empty:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            df.to_parquet(path, index=False)
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    output = df.copy()
    if path.exists():
        output = pd.concat([pd.read_parquet(path), output], ignore_index=True)
    missing = [key for key in dedupe_keys if key not in output.columns]
    if missing:
        raise ValueError(f"dedupe_keys not found in DataFrame: {missing}")
    output["trade_date"] = pd.to_datetime(output["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    output = output.dropna(subset=["trade_date"])
    output = output.drop_duplicates(dedupe_keys, keep="last")
    sort_cols = [column for column in ["trade_date", "order_book_id", "index_id", "adjust_type"] if column in output.columns]
    output = output.sort_values(sort_cols).reset_index(drop=True) if sort_cols else output.reset_index(drop=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    output.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)
    return path


def _update_prices(run_id: str, task: DailyUpdateTask, source: RQDataSource, *, batch_size: int) -> DailyUpdateResult:
    symbols = _load_symbols()
    output_paths = [Path(value) for value in task.output_path.split(";") if value]
    path_by_adjust = {path.parent.name.replace("prices_1d_", ""): path for path in output_paths}
    total_rows = 0
    written: list[str] = []
    for adjust_type in ["pre", "none"]:
        frames = [
            source.get_daily_prices(batch, start=task.start_date, end=task.end_date, adjust_type=adjust_type)
            for batch in _batches(symbols, batch_size)
        ]
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        path = merge_partition_file(
            frame,
            path_by_adjust[adjust_type],
            dedupe_keys=["trade_date", "order_book_id", "adjust_type"],
        )
        total_rows += len(frame)
        written.append(str(path))
    return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", total_rows, ";".join(written))


def _update_valuation(run_id: str, task: DailyUpdateTask, source: RQDataSource, *, batch_size: int) -> DailyUpdateResult:
    symbols = _load_symbols()
    frames = [
        source.get_valuation_factors(batch, task.start_date, task.end_date)
        for batch in _batches(symbols, batch_size)
    ]
    frame = pd.concat([item for item in frames if not item.empty], ignore_index=True) if frames else pd.DataFrame(columns=VALUATION_COLUMNS)
    path = merge_partition_file(frame, Path(task.output_path), dedupe_keys=["trade_date", "order_book_id"])
    return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", len(frame), str(path))


def _update_industry(run_id: str, task: DailyUpdateTask, source: RQDataSource) -> DailyUpdateResult:
    symbols = _load_symbols()
    frames = [
        source.get_industry_classification(symbols, trade_date=trade_date, source=DEFAULT_INDUSTRY_SOURCE, level=1)
        for trade_date in _trading_dates(task.start_date, task.end_date)
    ]
    frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    path = merge_partition_file(frame, Path(task.output_path), dedupe_keys=["trade_date", "order_book_id"])
    return DailyUpdateResult(run_id, task.dataset, task.start_date, task.end_date, task.year, "success", len(frame), str(path))


def _update_index_members(run_id: str, task: DailyUpdateTask, source: RQDataSource) -> DailyUpdateResult:
    paths = [Path(value) for value in task.output_path.split(";") if value]
    component_frames: list[pd.DataFrame] = []
    weight_frames: list[pd.DataFrame] = []
    for index_id in MEMBERSHIP_INDEX_IDS:
        for trade_date in _trading_dates(task.start_date, task.end_date):
            component_frames.append(source.get_index_components(index_id, trade_date))
            weight_frames.append(source.get_index_weights(index_id, trade_date))
    components = pd.concat(component_frames, ignore_index=True) if component_frames else pd.DataFrame()
    weights = pd.concat(weight_frames, ignore_index=True) if weight_frames else pd.DataFrame()
    component_path = merge_partition_file(components, paths[0], dedupe_keys=["trade_date", "index_id", "order_book_id"])
    weight_path = merge_partition_file(weights, paths[1], dedupe_keys=["trade_date", "index_id", "order_book_id"])
    return DailyUpdateResult(
        run_id,
        task.dataset,
        task.start_date,
        task.end_date,
        task.year,
        "success",
        len(components),
        f"{component_path};{weight_path}",
    )


def _load_symbols() -> list[str]:
    frame = read_single_file("instruments", "instruments.parquet")
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame = frame[frame["order_book_id"].str.endswith((".XSHG", ".XSHE"), na=False)]
    return sorted(frame["order_book_id"].dropna().drop_duplicates().tolist())


def _trading_dates(start_date: str, end_date: str) -> list[str]:
    calendar = read_single_file("trading_calendar", "trading_calendar.parquet")
    frame = calendar.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame = frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)]
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(bool)]
    return frame["trade_date"].dropna().drop_duplicates().sort_values().tolist()


def _batches(items: list[str], batch_size: int) -> list[list[str]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


def _append_daily_status(result: DailyUpdateResult) -> None:
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "run_id": result.run_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "dataset": result.dataset,
        "start_date": result.start_date,
        "end_date": result.end_date,
        "year": result.year or "",
        "status": result.status,
        "row_count": result.row_count,
        "output_files": result.output_files,
        "error": result.error,
    }
    frame = pd.DataFrame([row], columns=STATUS_COLUMNS)
    frame.to_csv(STATUS_PATH, mode="a", header=not STATUS_PATH.exists(), index=False)
