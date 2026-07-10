from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

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

    if start_date:
        target_start = date.fromisoformat(start_date)
    elif latest_date:
        target_start = date.fromisoformat(latest_date) + timedelta(days=1)
    else:
        raise ValueError("start_date is required when data lake has no latest date")

    if target_start > target_end:
        return DailyUpdatePlan(
            start_date=target_start.isoformat(),
            end_date=end_date,
            latest_date=latest_date,
            no_op=True,
            tasks=[_no_op_task(dataset, target_start.isoformat(), end_date) for dataset in selected],
        )

    update_days = (target_end - target_start).days + 1
    if update_days > max_update_days and not force:
        raise ValueError(
            f"daily update range is too large: {update_days} days; use backfill workflow or --force"
        )

    tasks: list[DailyUpdateTask] = []
    for dataset in selected:
        if dataset == "calendar":
            tasks.append(_calendar_task(root, target_start, target_end, force))
        elif dataset == "instruments":
            tasks.append(_instruments_task(root, target_start, target_end, force))
        else:
            for year in range(target_start.year, target_end.year + 1):
                year_start = max(target_start, date(year, 1, 1))
                year_end = min(target_end, date(year, 12, 31))
                if year_start <= year_end:
                    tasks.append(_partitioned_task(root, dataset, year, year_start, year_end, force))

    return DailyUpdatePlan(
        start_date=target_start.isoformat(),
        end_date=end_date,
        latest_date=latest_date,
        no_op=False,
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


def _no_op_task(dataset: str, start_date: str, end_date: str) -> DailyUpdateTask:
    return DailyUpdateTask(dataset, None, start_date, end_date, "", True, "no-op", "already covered")


def _calendar_task(root: Path, start: date, end: date, force: bool) -> DailyUpdateTask:
    path = root / "trading_calendar" / "trading_calendar.parquet"
    if force:
        return DailyUpdateTask("calendar", None, start.isoformat(), end.isoformat(), str(path), False, "rebuild", "force")
    if _file_covers(path, start.isoformat(), end.isoformat()):
        return DailyUpdateTask("calendar", None, start.isoformat(), end.isoformat(), str(path), True, "skip", "covered")
    return DailyUpdateTask(
        "calendar",
        None,
        start.isoformat(),
        end.isoformat(),
        str(path),
        False,
        "extend" if path.exists() else "create",
        "missing dates",
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
    if force:
        return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, False, "rebuild", "force")
    if all(_file_covers(path, start.isoformat(), end.isoformat()) for path in outputs):
        return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, True, "skip", "covered")
    if all(path.exists() for path in outputs):
        return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, False, "extend", "missing dates")
    return DailyUpdateTask(dataset, year, start.isoformat(), end.isoformat(), output_text, False, "create", "missing partition")


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
