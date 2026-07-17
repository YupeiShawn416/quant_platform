from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


DEFAULT_SNAPSHOT_TIMES = ["09:45", "09:55", "10:00", "14:30", "14:45", "14:55"]
CORE_SNAPSHOT_TIMES = ["09:55", "10:00"]
STATUS_COLUMNS = [
    "run_id",
    "dataset",
    "start_date",
    "end_date",
    "year",
    "month",
    "snapshot_time",
    "batch_id",
    "symbol_count",
    "row_count",
    "status",
    "error",
    "output_file",
    "created_at",
]
STATUS_PATH = settings.data_root_path / "update_logs" / "intraday_snapshot_update_status.csv"


@dataclass(frozen=True)
class IntradaySnapshotTask:
    year: int
    month: int
    start_date: str
    end_date: str
    output_path: str
    should_skip: bool
    action: str
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "year": self.year,
            "month": self.month,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "output_path": self.output_path,
            "should_skip": self.should_skip,
            "action": self.action,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IntradaySnapshotPlan:
    start_date: str
    end_date: str
    snapshot_times: list[str]
    dry_run: bool
    overwrite: bool
    no_op: bool
    tasks: list[IntradaySnapshotTask]

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date,
            "end_date": self.end_date,
            "snapshot_times": self.snapshot_times,
            "dry_run": self.dry_run,
            "overwrite": self.overwrite,
            "no_op": self.no_op,
            "tasks": [task.to_dict() for task in self.tasks],
        }


def normalize_snapshot_times(snapshot_times: str | list[str] | None = None) -> list[str]:
    if snapshot_times is None:
        values = DEFAULT_SNAPSHOT_TIMES
    elif isinstance(snapshot_times, str):
        values = [item.strip() for item in snapshot_times.split(",") if item.strip()]
    else:
        values = [item.strip() for item in snapshot_times if item.strip()]
    unknown = sorted(set(values) - set(DEFAULT_SNAPSHOT_TIMES))
    if unknown:
        raise ValueError(f"unsupported snapshot_time: {', '.join(unknown)}")
    return sorted(dict.fromkeys(values), key=DEFAULT_SNAPSHOT_TIMES.index)


def build_intraday_snapshot_plan(
    *,
    start_date: str,
    end_date: str,
    snapshot_times: str | list[str] | None = None,
    data_root: str | Path | None = None,
    overwrite: bool = False,
    dry_run: bool = True,
) -> IntradaySnapshotPlan:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start_date must be <= end_date")
    times = normalize_snapshot_times(snapshot_times)
    tasks: list[IntradaySnapshotTask] = []
    for year, month, month_start, month_end in _month_ranges(start, end):
        output = root / "intraday_snapshots" / f"year={year}" / f"month={month:02d}.parquet"
        should_skip, reason = _should_skip_partition(output, month_start, month_end, times, overwrite=overwrite)
        tasks.append(
            IntradaySnapshotTask(
                year=year,
                month=month,
                start_date=month_start.isoformat(),
                end_date=month_end.isoformat(),
                output_path=str(output),
                should_skip=should_skip,
                action="overwrite" if overwrite else ("skip" if should_skip else "append"),
                reason=reason,
            )
        )
    return IntradaySnapshotPlan(
        start_date=start_date,
        end_date=end_date,
        snapshot_times=times,
        dry_run=dry_run,
        overwrite=overwrite,
        no_op=all(task.should_skip for task in tasks),
        tasks=tasks,
    )


def render_intraday_snapshot_plan(plan: IntradaySnapshotPlan) -> str:
    lines = [
        "# Intraday Snapshot Plan",
        "",
        f"start_date={plan.start_date}",
        f"end_date={plan.end_date}",
        f"snapshot_times={','.join(plan.snapshot_times)}",
        f"dry_run={plan.dry_run}",
        f"overwrite={plan.overwrite}",
        f"no_op={plan.no_op}",
        "",
        "| year | month | start | end | skip | action | output | reason |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for task in plan.tasks:
        lines.append(
            f"| {task.year} | {task.month:02d} | {task.start_date} | {task.end_date} | "
            f"{task.should_skip} | {task.action} | {task.output_path} | {task.reason} |"
        )
    return "\n".join(lines) + "\n"


def _month_ranges(start: date, end: date) -> list[tuple[int, int, date, date]]:
    result: list[tuple[int, int, date, date]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        next_month = date(cursor.year + int(cursor.month == 12), 1 if cursor.month == 12 else cursor.month + 1, 1)
        month_start = max(start, cursor)
        month_end = min(end, next_month - pd.Timedelta(days=1).to_pytimedelta())
        result.append((cursor.year, cursor.month, month_start, month_end))
        cursor = next_month
    return result


def _should_skip_partition(path: Path, start: date, end: date, snapshot_times: list[str], *, overwrite: bool) -> tuple[bool, str]:
    if overwrite or not path.exists():
        return False, ""
    try:
        frame = pd.read_parquet(path, columns=["trade_date", "snapshot_time"])
    except Exception as exc:
        return False, f"cannot read existing partition: {type(exc).__name__}"
    if frame.empty:
        return False, "existing partition is empty"
    frame["trade_date"] = pd.to_datetime(frame["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    actual_dates = set(frame["trade_date"].dropna().astype(str))
    required_dates = set(pd.date_range(start, end).strftime("%Y-%m-%d"))
    actual_times = set(frame["snapshot_time"].dropna().astype(str))
    if required_dates.issubset(actual_dates) and set(snapshot_times).issubset(actual_times):
        return True, "exists"
    return False, "partial existing partition"
