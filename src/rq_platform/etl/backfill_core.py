from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file, write_by_year, write_single_file
from rq_platform.data_sources.rqdata_source import (
    DEFAULT_INDUSTRY_SOURCE,
    RQDataSource,
    VALUATION_COLUMNS,
)
from rq_platform.etl.backfill_plan import (
    BackfillTask,
    build_backfill_plan,
    normalize_datasets,
    require_full_backfill_confirmation,
)
from rq_platform.etl.update_index_membership import (
    DEFAULT_INDEX_IDS as MEMBERSHIP_INDEX_IDS,
    write_index_components,
    write_index_weights,
)
from rq_platform.etl.update_index_prices import DEFAULT_INDEX_IDS, write_index_prices
from rq_platform.etl.update_industry import write_industry_classification
from rq_platform.etl.update_status import append_status
from rq_platform.etl.update_tradability import update_tradability_dataset
from rq_platform.settings import settings


STATUS_PATH = settings.data_root_path / "update_logs" / "backfill_2016_present_status.csv"


@dataclass
class BackfillResult:
    dataset: str
    year: int | None
    status: str
    row_count: int = 0
    output_files: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "year": self.year,
            "status": self.status,
            "row_count": self.row_count,
            "output_files": self.output_files,
            "error": self.error,
        }


def plan_core_backfill(
    *,
    start_date: str,
    end_date: str,
    datasets: list[str] | str,
    years: list[int] | None = None,
    force: bool = False,
) -> list[BackfillTask]:
    return build_backfill_plan(
        start_date=start_date,
        end_date=end_date,
        datasets=normalize_datasets(datasets),
        years=years,
        force=force,
    )


def run_core_backfill(
    *,
    start_date: str,
    end_date: str,
    datasets: list[str] | str,
    years: list[int] | None = None,
    force: bool = False,
    dry_run: bool = False,
    smoke: bool = False,
    confirm_full_backfill: bool = False,
    max_securities: int | None = None,
    batch_size: int = 300,
    source: RQDataSource | None = None,
) -> list[BackfillResult | dict[str, Any]]:
    if smoke:
        start_date, end_date = _smoke_dates(start_date, end_date)
        max_securities = max_securities or 20
    require_full_backfill_confirmation(
        start_date=start_date,
        end_date=end_date,
        dry_run=dry_run,
        smoke=smoke,
        confirm_full_backfill=confirm_full_backfill,
    )
    tasks = plan_core_backfill(
        start_date=start_date,
        end_date=end_date,
        datasets=datasets,
        years=years,
        force=force,
    )
    if dry_run:
        return [task.to_dict() for task in tasks]

    data_source = source or RQDataSource()
    results: list[BackfillResult] = []
    for task in tasks:
        if task.should_skip:
            result = BackfillResult(task.dataset, task.year, "skipped", error=task.reason)
            results.append(result)
            _write_status(task, result)
            continue
        try:
            result = _run_task(task, data_source, max_securities=max_securities, batch_size=batch_size)
        except Exception as exc:
            result = BackfillResult(task.dataset, task.year, "failed", error=f"{type(exc).__name__}: {exc}")
        results.append(result)
        _write_status(task, result)
    return results


def render_plan(tasks: list[BackfillTask | dict[str, Any]]) -> str:
    rows = [task.to_dict() if isinstance(task, BackfillTask) else task for task in tasks]
    lines = [
        "# Backfill Plan",
        "",
        "| dataset | year | start | end | skip | action | output | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['dataset']} | {row.get('year') or ''} | {row['start_date']} | {row['end_date']} | "
            f"{row['should_skip']} | {row.get('action') or ''} | {row['output_path']} | "
            f"{row.get('reason') or ''} |"
        )
    return "\n".join(lines) + "\n"


def _run_task(
    task: BackfillTask,
    source: RQDataSource,
    *,
    max_securities: int | None,
    batch_size: int,
) -> BackfillResult:
    if task.dataset == "instruments":
        frame = source.get_instruments()
        path = write_single_file(frame, "instruments", "instruments.parquet")
        return BackfillResult(task.dataset, task.year, "success", len(frame), str(path))
    if task.dataset == "calendar":
        frame = source.get_trading_calendar(task.start_date, task.end_date)
        path = merge_trading_calendar_file(frame, Path(task.output_path), force=task.action == "rebuild")
        rows = len(pd.read_parquet(path, columns=["trade_date"]))
        return BackfillResult(task.dataset, task.year, "success", rows, str(path))
    if task.dataset == "index_prices":
        frame = source.get_index_prices(DEFAULT_INDEX_IDS, task.start_date, task.end_date)
        path = write_index_prices(frame, year=int(task.year))
        return BackfillResult(task.dataset, task.year, "success", len(frame), str(path))
    if task.dataset == "prices":
        return _backfill_prices(task, source, max_securities=max_securities, batch_size=batch_size)
    if task.dataset == "tradability":
        result = update_tradability_dataset(year=int(task.year), adjust_type="pre")
        return BackfillResult(task.dataset, task.year, "success", result["rows"], result["path"])
    if task.dataset == "valuation":
        return _backfill_valuation(task, source, max_securities=max_securities, batch_size=batch_size)
    if task.dataset == "industry":
        return _backfill_industry(task, source, max_securities=max_securities)
    if task.dataset == "index_members":
        return _backfill_index_members(task, source)
    raise ValueError(f"unsupported dataset: {task.dataset}")


def _backfill_prices(
    task: BackfillTask,
    source: RQDataSource,
    *,
    max_securities: int | None,
    batch_size: int,
) -> BackfillResult:
    symbols = _load_symbols(max_securities)
    output_files: list[str] = []
    total_rows = 0
    for adjust_type in ["pre", "none"]:
        for batch_symbols in _batches(symbols, batch_size):
            frame = source.get_daily_prices(
                batch_symbols,
                start=task.start_date,
                end=task.end_date,
                adjust_type=adjust_type,
            )
            paths = write_by_year(
                frame,
                f"prices_1d_{adjust_type}",
                date_col="trade_date",
                dedupe_keys=["trade_date", "order_book_id", "adjust_type"],
            )
            output_files.extend(str(path) for path in paths)
            total_rows += len(frame)
    return BackfillResult(task.dataset, task.year, "success", total_rows, ";".join(sorted(set(output_files))))


def merge_trading_calendar_file(new_frame: pd.DataFrame, path: Path, *, force: bool = False) -> Path:
    if "trade_date" not in new_frame.columns:
        raise ValueError("trade_date column is required for trading calendar backfill")

    path.parent.mkdir(parents=True, exist_ok=True)
    frames = [new_frame.copy()]
    if path.exists() and not force:
        frames.insert(0, pd.read_parquet(path))

    output = pd.concat(frames, ignore_index=True)
    output["trade_date"] = pd.to_datetime(output["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    output = output.dropna(subset=["trade_date"])
    output = output.drop_duplicates(["trade_date"], keep="last")
    output = output.sort_values("trade_date").reset_index(drop=True)

    tmp_path = path.with_name(f".{path.name}.tmp")
    output.to_parquet(tmp_path, index=False)
    tmp_path.replace(path)
    return path


def _backfill_valuation(
    task: BackfillTask,
    source: RQDataSource,
    *,
    max_securities: int | None,
    batch_size: int,
) -> BackfillResult:
    symbols = _load_symbols(max_securities)
    frames: list[pd.DataFrame] = []
    for batch_symbols in _batches(symbols, batch_size):
        frame = source.get_valuation_factors(batch_symbols, task.start_date, task.end_date)
        if not frame.empty:
            frames.append(frame)
    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=VALUATION_COLUMNS)
    paths = write_by_year(output, "valuation_1d", date_col="trade_date", dedupe_keys=["trade_date", "order_book_id"])
    return BackfillResult(task.dataset, task.year, "success", len(output), ";".join(str(path) for path in paths))


def _backfill_industry(
    task: BackfillTask,
    source: RQDataSource,
    *,
    max_securities: int | None,
) -> BackfillResult:
    symbols = _load_symbols(max_securities)
    dates = _trading_dates(task.start_date, task.end_date)
    frames = [
        source.get_industry_classification(symbols, trade_date=trade_date, source=DEFAULT_INDUSTRY_SOURCE, level=1)
        for trade_date in dates
    ]
    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    path = write_industry_classification(output, year=int(task.year))
    return BackfillResult(task.dataset, task.year, "success", len(output), str(path))


def _backfill_index_members(task: BackfillTask, source: RQDataSource) -> BackfillResult:
    dates = _trading_dates(task.start_date, task.end_date)
    component_frames: list[pd.DataFrame] = []
    weight_frames: list[pd.DataFrame] = []
    for index_id in MEMBERSHIP_INDEX_IDS:
        for trade_date in dates:
            component_frames.append(source.get_index_components(index_id, trade_date))
            weight_frames.append(source.get_index_weights(index_id, trade_date))
    components = pd.concat(component_frames, ignore_index=True) if component_frames else pd.DataFrame()
    weights = pd.concat(weight_frames, ignore_index=True) if weight_frames else pd.DataFrame()
    component_path = write_index_components(components, year=int(task.year))
    weight_path = write_index_weights(weights, year=int(task.year))
    return BackfillResult(
        task.dataset,
        task.year,
        "success",
        len(components),
        f"{component_path};{weight_path}",
    )


def _load_symbols(max_securities: int | None = None) -> list[str]:
    instruments = read_single_file("instruments", "instruments.parquet")
    frame = instruments.copy()
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame = frame[frame["order_book_id"].str.endswith((".XSHG", ".XSHE"), na=False)]
    symbols = sorted(frame["order_book_id"].dropna().drop_duplicates().tolist())
    return symbols[:max_securities] if max_securities else symbols


def _trading_dates(start_date: str, end_date: str) -> list[str]:
    try:
        calendar = read_single_file("trading_calendar", "trading_calendar.parquet")
        frame = calendar.copy()
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame = frame[(frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)]
        if "is_open" in frame.columns:
            frame = frame[frame["is_open"].astype(bool)]
        return frame["trade_date"].drop_duplicates().sort_values().tolist()
    except FileNotFoundError:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        dates = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                dates.append(current.isoformat())
            current += timedelta(days=1)
        return dates


def _batches(items: list[str], batch_size: int) -> list[list[str]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


def _smoke_dates(start_date: str, end_date: str) -> tuple[str, str]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    smoke_end = min(start + timedelta(days=9), end)
    return start.isoformat(), smoke_end.isoformat()


def _write_status(task: BackfillTask, result: BackfillResult) -> None:
    append_status(
        STATUS_PATH,
        {
            "dataset": result.dataset,
            "adjust_type": "",
            "year": result.year or "",
            "batch_id": "",
            "start_date": task.start_date,
            "end_date": task.end_date,
            "symbol_count": "",
            "status": result.status,
            "row_count": result.row_count,
            "output_files": result.output_files,
            "error": result.error,
        },
    )
