from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


SUPPORTED_DATASETS = [
    "prices",
    "index_prices",
    "calendar",
    "instruments",
    "tradability",
    "valuation",
    "industry",
    "index_members",
]


@dataclass(frozen=True)
class BackfillTask:
    dataset: str
    year: int | None
    start_date: str
    end_date: str
    output_path: str
    should_skip: bool
    reason: str = ""
    action: str = ""

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "year": self.year,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "output_path": self.output_path,
            "should_skip": self.should_skip,
            "reason": self.reason,
            "action": self.action,
        }


def build_backfill_plan(
    *,
    start_date: str,
    end_date: str,
    datasets: list[str],
    years: list[int] | None = None,
    force: bool = False,
    data_root: str | Path | None = None,
) -> list[BackfillTask]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start_date must not be after end_date")
    normalized = normalize_datasets(datasets)
    selected_years = years or list(range(start.year, end.year + 1))
    tasks: list[BackfillTask] = []

    for dataset in normalized:
        if dataset == "calendar":
            output = root / "trading_calendar" / "trading_calendar.parquet"
            tasks.append(_calendar_task(output, start_date, end_date, force))
            continue
        if dataset == "instruments":
            output = root / "instruments" / "instruments.parquet"
            tasks.append(_single_file_task(dataset, output, start_date, end_date, force))
            continue
        for year in selected_years:
            year_start = max(start, date(year, 1, 1))
            year_end = min(end, date(year, 12, 31))
            if year_start > year_end:
                continue
            outputs = _output_paths(root, dataset, year)
            tasks.append(_task(dataset, year, year_start.isoformat(), year_end.isoformat(), outputs, force))
    return tasks


def normalize_datasets(datasets: list[str] | str) -> list[str]:
    if isinstance(datasets, str):
        raw = [item.strip() for item in datasets.split(",")]
    else:
        raw = datasets
    values = [item for item in raw if item]
    unknown = sorted(set(values) - set(SUPPORTED_DATASETS))
    if unknown:
        raise ValueError(f"unknown datasets: {', '.join(unknown)}")
    return values


def require_full_backfill_confirmation(
    *,
    start_date: str,
    end_date: str,
    dry_run: bool,
    smoke: bool,
    confirm_full_backfill: bool,
) -> None:
    if dry_run or smoke:
        return
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    spans_multiple_years = start.year < end.year or (end - start).days > 90
    if spans_multiple_years and not confirm_full_backfill:
        raise ValueError("full backfill requires --confirm-full-backfill")


def _task(
    dataset: str,
    year: int | None,
    start_date: str,
    end_date: str,
    outputs: list[Path],
    force: bool,
) -> BackfillTask:
    exists = _outputs_exist(dataset, outputs, start_date, end_date)
    return BackfillTask(
        dataset=dataset,
        year=year,
        start_date=start_date,
        end_date=end_date,
        output_path=";".join(str(output) for output in outputs),
        should_skip=exists and not force,
        reason="exists" if exists and not force else "",
        action="skip" if exists and not force else "create",
    )


def _single_file_task(
    dataset: str,
    output: Path,
    start_date: str,
    end_date: str,
    force: bool,
) -> BackfillTask:
    exists = output.exists()
    if force:
        action = "rebuild"
        should_skip = False
        reason = "force"
    elif exists:
        action = "skip"
        should_skip = True
        reason = "exists"
    else:
        action = "create"
        should_skip = False
        reason = "missing"
    return BackfillTask(
        dataset=dataset,
        year=None,
        start_date=start_date,
        end_date=end_date,
        output_path=str(output),
        should_skip=should_skip,
        reason=reason,
        action=action,
    )


def _calendar_task(output: Path, start_date: str, end_date: str, force: bool) -> BackfillTask:
    coverage = _calendar_coverage(output, start_date, end_date)
    requested_years = set(range(date.fromisoformat(start_date).year, date.fromisoformat(end_date).year + 1))
    covered_years = coverage["covered_years"]
    missing_years = sorted(requested_years - covered_years)
    existing_range = coverage["existing_date_range"]
    requested_range = f"{start_date}..{end_date}"

    if force:
        action = "rebuild"
        should_skip = False
        reason = f"force requested_date_range={requested_range}"
    elif not output.exists():
        action = "create"
        should_skip = False
        reason = f"missing requested_date_range={requested_range}"
    elif coverage["covers_requested_range"] and not missing_years:
        action = "skip"
        should_skip = True
        reason = f"covered existing_date_range={existing_range} requested_date_range={requested_range}"
    else:
        action = "extend"
        should_skip = False
        missing = ",".join(str(year) for year in missing_years) or "partial-range"
        reason = (
            f"missing_years={missing} existing_date_range={existing_range} "
            f"requested_date_range={requested_range}"
        )

    return BackfillTask(
        dataset="calendar",
        year=None,
        start_date=start_date,
        end_date=end_date,
        output_path=str(output),
        should_skip=should_skip,
        reason=reason,
        action=action,
    )


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


def _outputs_exist(dataset: str, outputs: list[Path], start_date: str, end_date: str) -> bool:
    if not all(path.exists() for path in outputs):
        return False
    return True


def _calendar_coverage(path: Path, start_date: str, end_date: str) -> dict:
    empty = {
        "covered_years": set(),
        "existing_date_range": "missing",
        "covers_requested_range": False,
    }
    if not path.exists():
        return empty
    try:
        frame = pd.read_parquet(path, columns=["trade_date"])
        dates = pd.to_datetime(frame["trade_date"], errors="coerce").dropna()
    except Exception:
        return empty
    if dates.empty:
        return empty
    return {
        "covered_years": set(int(year) for year in dates.dt.year.dropna().unique()),
        "existing_date_range": f"{dates.min().date().isoformat()}..{dates.max().date().isoformat()}",
        "covers_requested_range": (
            int(dates.min().year) <= date.fromisoformat(start_date).year
            and dates.max().date().isoformat() >= end_date
        ),
    }
