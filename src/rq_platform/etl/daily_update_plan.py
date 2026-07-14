from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.settings import settings


DEFAULT_DAILY_DATASETS = [
    "calendar",
    "instruments",
    "index_prices",
    "prices",
    "tradability",
    "valuation",
    "industry",
    "index_members",
]
PARTITIONED_DATASETS = {"index_prices", "prices", "tradability", "valuation", "industry", "index_members"}
SINGLE_FILE_DATASETS = {"calendar", "instruments"}
SUPPORTED_DATASETS = set(DEFAULT_DAILY_DATASETS)
MAX_DAILY_UPDATE_DAYS = 31
CORE_DATASETS = {"prices", "index_prices", "tradability", "valuation", "industry", "index_members"}
STATUS_PATH = settings.data_root_path / "update_logs" / "daily_update_status.csv"


@dataclass(frozen=True)
class DailyUpdateTask:
    dataset: str
    year: int | None
    start_date: str
    end_date: str
    output_path: str
    should_skip: bool
    action: str
    reason: str = ""
    actual_max_date: str | None = None
    status_mismatch: bool = False

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "year": self.year,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "output_path": self.output_path,
            "should_skip": self.should_skip,
            "action": self.action,
            "reason": self.reason,
            "actual_max_date": self.actual_max_date,
            "status_mismatch": self.status_mismatch,
        }


@dataclass(frozen=True)
class DailyUpdatePlan:
    start_date: str
    end_date: str
    latest_date: str | None
    no_op: bool
    tasks: list[DailyUpdateTask]

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "latest_date": self.latest_date,
            "no_op": self.no_op,
            "tasks": [task.to_dict() for task in self.tasks],
        }


def normalize_datasets(datasets: list[str] | str | None) -> list[str]:
    if datasets is None:
        values = DEFAULT_DAILY_DATASETS
    elif isinstance(datasets, str):
        values = [item.strip() for item in datasets.split(",") if item.strip()]
    else:
        values = [item for item in datasets if item]
    unknown = sorted(set(values) - SUPPORTED_DATASETS)
    if unknown:
        raise ValueError(f"unknown datasets: {', '.join(unknown)}")
    return values


def get_data_lake_latest_date(data_root: str | Path | None = None) -> str | None:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    calendar_path = root / "trading_calendar" / "trading_calendar.parquet"
    if calendar_path.exists():
        latest = _latest_date_in_file(calendar_path)
        if latest:
            return latest
    latest_values = [
        _latest_date_in_file(path)
        for path in root.glob("*/*.parquet")
        if path.name.endswith(".parquet")
    ]
    latest_values = [value for value in latest_values if value]
    return max(latest_values) if latest_values else None


def build_daily_update_plan(
    *,
    end_date: str,
    start_date: str | None = None,
    datasets: list[str] | str | None = None,
    force: bool = False,
    data_root: str | Path | None = None,
    max_update_days: int = MAX_DAILY_UPDATE_DAYS,
) -> DailyUpdatePlan:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    selected = normalize_datasets(datasets)
    latest_date = get_data_lake_latest_date(root)
    target_end = date.fromisoformat(end_date)

    explicit_start = date.fromisoformat(start_date) if start_date else None

    target_start = explicit_start
    if target_start is None:
        latest_by_dataset = [
            _dataset_actual_max_date(root, dataset) for dataset in selected if dataset != "instruments"
        ]
        latest_by_dataset = [value for value in latest_by_dataset if value]
        if latest_by_dataset:
            target_start = date.fromisoformat(min(latest_by_dataset)) + timedelta(days=1)
        elif latest_date:
            target_start = date.fromisoformat(latest_date) + timedelta(days=1)
        else:
            raise ValueError("start_date is required when data lake has no latest date")

    if target_start > target_end:
        tasks = [
            _task_for_dataset(root, dataset, target_start, target_end, force, explicit_start=explicit_start)
            for dataset in selected
        ]
        return DailyUpdatePlan(
            start_date=target_start.isoformat(),
            end_date=end_date,
            latest_date=latest_date,
            no_op=all(task.should_skip for task in tasks),
            tasks=tasks,
        )

    update_days = (target_end - target_start).days + 1
    if update_days > max_update_days and not force:
        raise ValueError(
            f"daily update range is too large: {update_days} days; use backfill workflow or --force"
        )

    tasks: list[DailyUpdateTask] = []
    for dataset in selected:
        task_or_tasks = _task_for_dataset(root, dataset, target_start, target_end, force, explicit_start=explicit_start)
        if isinstance(task_or_tasks, list):
            tasks.extend(task_or_tasks)
        else:
            tasks.append(task_or_tasks)

    return DailyUpdatePlan(
        start_date=target_start.isoformat(),
        end_date=end_date,
        latest_date=latest_date,
        no_op=all(task.should_skip for task in tasks),
        tasks=tasks,
    )


def render_daily_update_plan(plan: DailyUpdatePlan) -> str:
    lines = [
        "# Daily Update Plan",
        "",
        f"latest_date={plan.latest_date or ''}",
        f"start_date={plan.start_date}",
        f"end_date={plan.end_date}",
        f"no_op={plan.no_op}",
        "",
        "| dataset | year | start | end | skip | action | output | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for task in plan.tasks:
        lines.append(
            f"| {task.dataset} | {task.year or ''} | {task.start_date} | {task.end_date} | "
            f"{task.should_skip} | {task.action} | {task.output_path} | {task.reason} |"
        )
    return "\n".join(lines) + "\n"


def _task_for_dataset(
    root: Path,
    dataset: str,
    start: date,
    end: date,
    force: bool,
    *,
    explicit_start: date | None,
) -> DailyUpdateTask | list[DailyUpdateTask]:
    dataset_start = start if explicit_start is not None else _dataset_next_start(root, dataset, start)
    if dataset_start > end:
        return _no_op_task(dataset, dataset_start.isoformat(), end.isoformat(), root)
    if dataset == "calendar":
        return _calendar_task(root, dataset_start, end, force)
    if dataset == "instruments":
        return _instruments_task(root, dataset_start, end, force)
    tasks: list[DailyUpdateTask] = []
    for year in range(dataset_start.year, end.year + 1):
        year_start = max(dataset_start, date(year, 1, 1))
        year_end = min(end, date(year, 12, 31))
        if year_start <= year_end:
            tasks.append(_partitioned_task(root, dataset, year, year_start, year_end, force))
    return tasks


def _no_op_task(dataset: str, start_date: str, end_date: str, root: Path) -> DailyUpdateTask:
    actual_max = _dataset_actual_max_date(root, dataset)
    mismatch = _status_success_but_not_covered(dataset, None, actual_max, end_date)
    return DailyUpdateTask(
        dataset,
        None,
        start_date,
        end_date,
        "",
        not mismatch,
        "repair_needed" if mismatch else "no-op",
        "status success but parquet not covered" if mismatch else "already covered",
        actual_max_date=actual_max,
        status_mismatch=mismatch,
    )


def _calendar_task(root: Path, start: date, end: date, force: bool) -> DailyUpdateTask:
    path = root / "trading_calendar" / "trading_calendar.parquet"
    actual_max = _latest_date_in_file(path)
    mismatch = _status_success_but_not_covered("calendar", None, actual_max, end.isoformat())
    if force:
        return DailyUpdateTask("calendar", None, start.isoformat(), end.isoformat(), str(path), False, "rebuild", "force", actual_max)
    if _file_covers(path, start.isoformat(), end.isoformat()):
        return DailyUpdateTask("calendar", None, start.isoformat(), end.isoformat(), str(path), True, "skip", "covered", actual_max, mismatch)
    return DailyUpdateTask(
        "calendar",
        None,
        start.isoformat(),
        end.isoformat(),
        str(path),
        False,
        "extend" if path.exists() else "create",
        "status success but parquet not covered" if mismatch else "missing dates",
        actual_max_date=actual_max,
        status_mismatch=mismatch,
    )


def _instruments_task(root: Path, start: date, end: date, force: bool) -> DailyUpdateTask:
    path = root / "instruments" / "instruments.parquet"
    if force:
        return DailyUpdateTask("instruments", None, start.isoformat(), end.isoformat(), str(path), False, "refresh", "force")
    if path.exists():
        return DailyUpdateTask("instruments", None, start.isoformat(), end.isoformat(), str(path), True, "skip", "exists")
    return DailyUpdateTask("instruments", None, start.isoformat(), end.isoformat(), str(path), False, "create", "missing")


def _partitioned_task(root: Path, dataset: str, year: int, start: date, end: date, force: bool) -> DailyUpdateTask:
    outputs = _output_paths(root, dataset, year)
    output_text = ";".join(str(path) for path in outputs)
    actual_max = _min_non_empty([_latest_date_in_file(path) for path in outputs])
    mismatch = _status_success_but_not_covered(dataset, year, actual_max, end.isoformat())
    if force:
        return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, False, "rebuild", "force", actual_max)
    if all(_file_covers(path, start.isoformat(), end.isoformat()) for path in outputs):
        return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, True, "skip", "covered", actual_max, mismatch)
    if all(path.exists() for path in outputs):
        return DailyUpdateTask(
            dataset,
            year,
            start.isoformat(),
            end.isoformat(),
            output_text,
            False,
            "repair_needed" if mismatch else "extend",
            "status success but parquet not covered" if mismatch else "missing dates",
            actual_max,
            mismatch,
        )
    return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, False, "create", "missing partition", actual_max, mismatch)


def _output_paths(root: Path, dataset: str, year: int) -> list[Path]:
    mapping = {
        "prices": [
            root / "prices_1d_pre" / f"year={year}.parquet",
            root / "prices_1d_none" / f"year={year}.parquet",
        ],
        "index_prices": [root / "index_prices_1d" / f"year={year}.parquet"],
        "tradability": [root / "tradability_1d" / f"year={year}.parquet"],
        "valuation": [root / "valuation_1d" / f"year={year}.parquet"],
        "industry": [root / "industry_classification" / f"year={year}.parquet"],
        "index_members": [
            root / "index_components" / f"year={year}.parquet",
            root / "index_weights" / f"year={year}.parquet",
        ],
    }
    return mapping[dataset]


def _dataset_next_start(root: Path, dataset: str, fallback_start: date) -> date:
    if dataset == "instruments":
        return fallback_start
    actual_max = _dataset_actual_max_date(root, dataset)
    if actual_max:
        return date.fromisoformat(actual_max) + timedelta(days=1)
    return fallback_start


def _dataset_actual_max_date(root: Path, dataset: str) -> str | None:
    if dataset == "calendar":
        return _latest_date_in_file(root / "trading_calendar" / "trading_calendar.parquet")
    if dataset == "instruments":
        return _latest_date_in_file(root / "instruments" / "instruments.parquet")
    latest_values: list[str | None] = []
    for year in range(1900, 2200):
        paths = _output_paths(root, dataset, year)
        existing = [path for path in paths if path.exists()]
        if not existing:
            continue
        latest_values.append(_min_non_empty([_latest_date_in_file(path) for path in existing]))
    return max([value for value in latest_values if value], default=None)


def _min_non_empty(values: list[str | None]) -> str | None:
    clean = [value for value in values if value]
    return min(clean) if clean else None


def _status_success_but_not_covered(dataset: str, year: int | None, actual_max: str | None, end_date: str) -> bool:
    status = _latest_status_row(dataset, year)
    if not status or str(status.get("status")) != "success":
        return False
    if actual_max is None or actual_max < end_date:
        return True
    return False


def _latest_status_row(dataset: str, year: int | None) -> dict[str, Any] | None:
    if not STATUS_PATH.exists():
        return None
    try:
        frame = pd.read_csv(STATUS_PATH)
    except Exception:
        return None
    if frame.empty or "dataset" not in frame.columns:
        return None
    items = frame[frame["dataset"].astype(str) == dataset]
    if year is not None and "year" in items.columns:
        year_values = pd.to_numeric(items["year"], errors="coerce")
        items = items[year_values == int(year)]
    if items.empty:
        return None
    return items.iloc[-1].to_dict()


def _file_covers(path: Path, start_date: str, end_date: str) -> bool:
    latest = _latest_date_in_file(path)
    earliest = _earliest_date_in_file(path)
    return bool(earliest and latest and earliest <= start_date and latest >= end_date)


def _latest_date_in_file(path: Path) -> str | None:
    return _date_bound_in_file(path, "max")


def _earliest_date_in_file(path: Path) -> str | None:
    return _date_bound_in_file(path, "min")


def _date_bound_in_file(path: Path, bound: str) -> str | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path, columns=["trade_date"])
    except Exception:
        return None
    if frame.empty or "trade_date" not in frame.columns:
        return None
    dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    if dates.empty:
        return None
    value = dates.max() if bound == "max" else dates.min()
    return value.strftime("%Y-%m-%d")
