from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from rq_platform.settings import settings


DATASETS = [
    "instruments",
    "trading_calendar",
    "prices_1d_pre",
    "prices_1d_none",
    "index_prices_1d",
    "tradability_1d",
    "valuation_1d",
    "industry_classification",
    "index_components",
    "index_weights",
]


@dataclass
class DatasetCoverage:
    dataset: str
    path: str
    exists: bool
    year: int | None = None
    rows: int = 0
    symbols: int | None = None
    min_date: str | None = None
    max_date: str | None = None
    duplicate_keys: int | None = None
    missing_years: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "dataset": self.dataset,
            "path": self.path,
            "exists": self.exists,
            "year": self.year,
            "rows": self.rows,
            "symbols": self.symbols,
            "min_date": self.min_date,
            "max_date": self.max_date,
            "duplicate_keys": self.duplicate_keys,
            "missing_years": self.missing_years,
            "error": self.error,
        }


def audit_data_lake(
    data_root: str | Path | None = None,
    datasets: Iterable[str] | None = None,
    expected_start_year: int = 2016,
    expected_end_year: int | None = None,
) -> pd.DataFrame:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    expected_end_year = expected_end_year or pd.Timestamp.today().year
    expected_years = set(range(expected_start_year, expected_end_year + 1))
    records: list[DatasetCoverage] = []

    for dataset in datasets or DATASETS:
        dataset_path = root / dataset
        if not dataset_path.exists():
            records.append(
                DatasetCoverage(
                    dataset=dataset,
                    path=str(dataset_path),
                    exists=False,
                    missing_years=_format_missing(expected_years),
                )
            )
            continue

        files = _dataset_files(dataset_path, dataset)
        if not files:
            records.append(DatasetCoverage(dataset=dataset, path=str(dataset_path), exists=True))
            continue

        years_seen: set[int] = set()
        for year, file_path in files:
            if year is not None:
                years_seen.add(year)
            records.append(_audit_file(dataset, file_path, year))

        missing = expected_years - years_seen if _is_partitioned_dataset(dataset_path) else set()
        if missing:
            records.append(
                DatasetCoverage(
                    dataset=dataset,
                    path=str(dataset_path),
                    exists=True,
                    missing_years=_format_missing(missing),
                )
            )

    return pd.DataFrame([record.to_dict() for record in records])


def write_audit_reports(
    frame: pd.DataFrame,
    output_dir: str | Path = "reports/generated",
) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    csv_path = output / "data_lake_coverage.csv"
    md_path = output / "data_lake_coverage.md"
    frame.to_csv(csv_path, index=False)
    md_path.write_text(render_audit_markdown(frame), encoding="utf-8")
    return md_path, csv_path


def render_audit_markdown(frame: pd.DataFrame) -> str:
    lines = ["# Data Lake Coverage", ""]
    if frame.empty:
        lines.append("No datasets found.")
        return "\n".join(lines) + "\n"
    columns = [
        "dataset",
        "year",
        "exists",
        "rows",
        "symbols",
        "min_date",
        "max_date",
        "duplicate_keys",
        "missing_years",
        "error",
    ]
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in frame[columns].fillna("").iterrows():
        lines.append("| " + " | ".join(str(row[column]) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def _dataset_files(dataset_path: Path, dataset: str) -> list[tuple[int | None, Path]]:
    year_files = sorted(dataset_path.glob("year=*.parquet"))
    if year_files:
        return [(_parse_year(path), path) for path in year_files]
    single = {
        "instruments": "instruments.parquet",
        "trading_calendar": "trading_calendar.parquet",
    }.get(dataset)
    if single and (dataset_path / single).exists():
        return [(None, dataset_path / single)]
    return [(None, path) for path in sorted(dataset_path.glob("*.parquet"))]


def _audit_file(dataset: str, path: Path, year: int | None) -> DatasetCoverage:
    try:
        frame = pd.read_parquet(path)
        min_date, max_date = _date_range(frame)
        return DatasetCoverage(
            dataset=dataset,
            path=str(path),
            exists=True,
            year=year,
            rows=int(len(frame)),
            symbols=_symbol_count(frame),
            min_date=min_date,
            max_date=max_date,
            duplicate_keys=_duplicate_count(frame),
        )
    except Exception as exc:
        return DatasetCoverage(
            dataset=dataset,
            path=str(path),
            exists=True,
            year=year,
            error=f"{type(exc).__name__}: {exc}",
        )


def _date_range(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    date_col = next((col for col in ["trade_date", "date", "listed_date"] if col in frame.columns), None)
    if date_col is None or frame.empty:
        return None, None
    dates = pd.to_datetime(frame[date_col], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")


def _symbol_count(frame: pd.DataFrame) -> int | None:
    if "order_book_id" in frame.columns:
        return int(frame["order_book_id"].astype(str).nunique())
    return None


def _duplicate_count(frame: pd.DataFrame) -> int | None:
    for keys in [
        ["trade_date", "order_book_id", "adjust_type"],
        ["trade_date", "order_book_id"],
        ["trade_date", "index_id", "order_book_id"],
    ]:
        if set(keys).issubset(frame.columns):
            return int(frame.duplicated(keys).sum())
    return None


def _is_partitioned_dataset(path: Path) -> bool:
    return any(path.glob("year=*.parquet"))


def _parse_year(path: Path) -> int | None:
    try:
        return int(path.stem.split("=", 1)[1])
    except Exception:
        return None


def _format_missing(years: Iterable[int]) -> str:
    return ",".join(str(year) for year in sorted(years))
