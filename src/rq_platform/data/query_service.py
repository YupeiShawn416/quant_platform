from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from rq_platform.settings import settings


SUPPORTED_START_DATE = "2016-01-04"
SUPPORTED_END_DATE = "2026-07-10"
MAX_QUERY_LIMIT = 50_000
DEFAULT_QUERY_LIMIT = 5_000


class DataQueryError(ValueError):
    pass


class DatasetNotFoundError(DataQueryError):
    pass


@dataclass(frozen=True)
class DatasetSpec:
    dataset: str
    description: str
    storage_name: str
    date_column: str | None
    primary_keys: tuple[str, ...]
    partitioned: bool = True
    filename: str | None = None

    def root(self, data_root: str | Path | None = None) -> Path:
        root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
        return root / self.storage_name


DATASET_SPECS: dict[str, DatasetSpec] = {
    "trading_calendar": DatasetSpec(
        dataset="trading_calendar",
        description="Trading calendar with trade dates.",
        storage_name="trading_calendar",
        date_column="trade_date",
        primary_keys=("trade_date",),
        partitioned=False,
        filename="trading_calendar.parquet",
    ),
    "instruments": DatasetSpec(
        dataset="instruments",
        description="Instrument metadata.",
        storage_name="instruments",
        date_column="listed_date",
        primary_keys=("order_book_id",),
        partitioned=False,
        filename="instruments.parquet",
    ),
    "prices_1d_pre": DatasetSpec(
        dataset="prices_1d_pre",
        description="Daily stock prices with pre adjustment.",
        storage_name="prices_1d_pre",
        date_column="trade_date",
        primary_keys=("trade_date", "order_book_id"),
    ),
    "prices_1d_none": DatasetSpec(
        dataset="prices_1d_none",
        description="Daily stock prices without adjustment.",
        storage_name="prices_1d_none",
        date_column="trade_date",
        primary_keys=("trade_date", "order_book_id"),
    ),
    "index_prices_1d": DatasetSpec(
        dataset="index_prices_1d",
        description="Daily index prices.",
        storage_name="index_prices_1d",
        date_column="trade_date",
        primary_keys=("trade_date", "order_book_id"),
    ),
    "tradability_1d": DatasetSpec(
        dataset="tradability_1d",
        description="Daily tradability flags.",
        storage_name="tradability_1d",
        date_column="trade_date",
        primary_keys=("trade_date", "order_book_id"),
    ),
    "valuation_1d": DatasetSpec(
        dataset="valuation_1d",
        description="Daily valuation metrics.",
        storage_name="valuation_1d",
        date_column="trade_date",
        primary_keys=("trade_date", "order_book_id"),
    ),
    "industry_classification": DatasetSpec(
        dataset="industry_classification",
        description="Industry classification by instrument.",
        storage_name="industry_classification",
        date_column="trade_date",
        primary_keys=("trade_date", "order_book_id"),
    ),
    "index_components": DatasetSpec(
        dataset="index_components",
        description="Index component membership.",
        storage_name="index_components",
        date_column="trade_date",
        primary_keys=("trade_date", "index_id", "order_book_id"),
    ),
    "index_weights": DatasetSpec(
        dataset="index_weights",
        description="Index component weights.",
        storage_name="index_weights",
        date_column="trade_date",
        primary_keys=("trade_date", "index_id", "order_book_id"),
    ),
    "cn_hxz_4_factors_monthly": DatasetSpec(
        dataset="cn_hxz_4_factors_monthly",
        description="Experimental CN-HXZ four factors, monthly.",
        storage_name="derived/hxz_factors",
        date_column=None,
        primary_keys=("month",),
        partitioned=False,
        filename="cn_hxz_4_factors_monthly.parquet",
    ),
    "cn_ff3_factors_monthly": DatasetSpec(
        dataset="cn_ff3_factors_monthly",
        description="Experimental China FF3 factors, monthly.",
        storage_name="derived/cn_ff3",
        date_column=None,
        primary_keys=("month",),
        partitioned=False,
        filename="cn_ff3_factors_monthly.parquet",
    ),
}


class DataQueryService:
    def __init__(self, data_root: str | Path | None = None):
        self.data_root = Path(data_root).resolve() if data_root is not None else settings.data_root_path

    def list_datasets(self) -> list[dict[str, Any]]:
        coverage = {item["dataset"]: item for item in self.coverage()["datasets"]}
        rows: list[dict[str, Any]] = []
        for spec in DATASET_SPECS.values():
            item = coverage.get(spec.dataset, {})
            rows.append(
                {
                    "dataset": spec.dataset,
                    "description": spec.description,
                    "date_range": {
                        "min_date": item.get("min_date"),
                        "max_date": item.get("max_date"),
                    },
                    "row_count": item.get("rows", 0),
                    "default_date_column": spec.date_column,
                    "primary_keys": list(spec.primary_keys),
                }
            )
        return rows

    def coverage(self) -> dict[str, Any]:
        datasets = [self.dataset_coverage(spec.dataset) for spec in DATASET_SPECS.values()]
        supported_start, supported_end = _supported_range_from_coverage(datasets)
        return {
            "supported_start_date": supported_start,
            "supported_end_date": supported_end,
            "datasets": datasets,
        }

    def dataset_coverage(self, dataset: str) -> dict[str, Any]:
        spec = get_dataset_spec(dataset)
        files = self._dataset_files(spec)
        years: list[int] = []
        row_count = 0
        min_date: str | None = None
        max_date: str | None = None
        for file_path in files:
            year = _parse_year(file_path)
            if year is not None:
                years.append(year)
            row_count += _parquet_rows(file_path)
            frame = self._safe_read_dates(file_path, spec.date_column)
            date_min, date_max = _date_range(frame, spec.date_column)
            min_date = _min_date(min_date, date_min)
            max_date = _max_date(max_date, date_max)
        return {
            "dataset": spec.dataset,
            "years": sorted(set(years)),
            "min_date": min_date,
            "max_date": max_date,
            "rows": row_count,
            "exists": bool(files),
        }

    def schema(self, dataset: str) -> list[dict[str, Any]]:
        spec = get_dataset_spec(dataset)
        files = self._dataset_files(spec)
        if not files:
            raise DatasetNotFoundError(f"dataset not found: {dataset}")
        frame = pd.read_parquet(files[0])
        return [
            {"name": column, "dtype": str(frame[column].dtype), "nullable": bool(frame[column].isna().any())}
            for column in frame.columns
        ]

    def query(
        self,
        dataset: str,
        *,
        start_date: str | None = None,
        end_date: str | None = None,
        order_book_ids: list[str] | None = None,
        fields: list[str] | None = None,
        limit: int = DEFAULT_QUERY_LIMIT,
        offset: int = 0,
    ) -> tuple[pd.DataFrame, bool]:
        if limit < 1:
            raise DataQueryError("limit must be >= 1")
        if limit > MAX_QUERY_LIMIT:
            raise DataQueryError(f"limit must be <= {MAX_QUERY_LIMIT}")
        if offset < 0:
            raise DataQueryError("offset must be >= 0")
        spec = get_dataset_spec(dataset)
        supported_start, supported_end = self.supported_date_range()
        _validate_supported_date_range(start_date, end_date, supported_start, supported_end)
        files = self._files_for_query(spec, start_date, end_date)
        if not files:
            raise DatasetNotFoundError(f"dataset not found: {dataset}")

        frames = [pd.read_parquet(path) for path in files]
        frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        frame = _filter_dates(frame, spec.date_column, start_date, end_date)
        frame = _filter_ids(frame, order_book_ids)
        frame = _project_fields(frame, fields)
        frame = _sort_frame(frame)

        window = frame.iloc[offset : offset + limit + 1].copy()
        has_more = len(window) > limit
        return window.head(limit).reset_index(drop=True), has_more

    def _dataset_files(self, spec: DatasetSpec) -> list[Path]:
        root = spec.root(self.data_root)
        if spec.partitioned:
            return sorted(root.glob("year=*.parquet"))
        if spec.filename and (root / spec.filename).exists():
            return [root / spec.filename]
        return sorted(root.glob("*.parquet"))

    def _files_for_query(
        self,
        spec: DatasetSpec,
        start_date: str | None,
        end_date: str | None,
    ) -> list[Path]:
        files = self._dataset_files(spec)
        if not spec.partitioned or not spec.date_column:
            return files
        years = _query_years(start_date, end_date)
        if not years:
            return files
        return [path for path in files if _parse_year(path) in years]

    def _safe_read_dates(self, path: Path, date_column: str | None) -> pd.DataFrame:
        if not date_column:
            return pd.DataFrame()
        try:
            return pd.read_parquet(path, columns=[date_column])
        except Exception:
            return pd.DataFrame()

    def supported_date_range(self) -> tuple[str, str]:
        datasets = [self.dataset_coverage(spec.dataset) for spec in DATASET_SPECS.values()]
        return _supported_range_from_coverage(datasets)


def get_dataset_spec(dataset: str) -> DatasetSpec:
    try:
        return DATASET_SPECS[dataset]
    except KeyError as exc:
        raise DatasetNotFoundError(f"unsupported dataset: {dataset}") from exc


def parse_csv_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _validate_supported_date_range(
    start_date: str | None,
    end_date: str | None,
    supported_start: str = SUPPORTED_START_DATE,
    supported_end: str = SUPPORTED_END_DATE,
) -> None:
    for field_name, value in [("start_date", start_date), ("end_date", end_date)]:
        if value:
            try:
                date.fromisoformat(value)
            except ValueError as exc:
                raise DataQueryError(f"{field_name} must be YYYY-MM-DD") from exc
    if start_date and start_date < supported_start:
        raise DataQueryError(f"start_date must be >= {supported_start}")
    if end_date and end_date > supported_end:
        raise DataQueryError(f"end_date must be <= {supported_end}")
    if start_date and end_date and start_date > end_date:
        raise DataQueryError("start_date must be <= end_date")


def _filter_dates(
    frame: pd.DataFrame,
    date_column: str | None,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    if frame.empty or not date_column or date_column not in frame.columns:
        return frame
    output = frame.copy()
    dates = pd.to_datetime(output[date_column], errors="coerce").dt.strftime("%Y-%m-%d")
    output[date_column] = dates
    if start_date:
        output = output[output[date_column] >= start_date]
    if end_date:
        output = output[output[date_column] <= end_date]
    return output


def _filter_ids(frame: pd.DataFrame, order_book_ids: list[str] | None) -> pd.DataFrame:
    if frame.empty or not order_book_ids:
        return frame
    candidate_cols = [column for column in ["order_book_id", "index_id"] if column in frame.columns]
    if not candidate_cols:
        return frame
    mask = False
    for column in candidate_cols:
        mask = mask | frame[column].astype(str).isin(order_book_ids)
    return frame[mask]


def _project_fields(frame: pd.DataFrame, fields: list[str] | None) -> pd.DataFrame:
    if not fields:
        return frame
    missing = [field for field in fields if field not in frame.columns]
    if missing:
        raise DataQueryError(f"unknown fields: {', '.join(missing)}")
    return frame[fields]


def _sort_frame(frame: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [
        column
        for column in ["trade_date", "listed_date", "index_id", "order_book_id"]
        if column in frame.columns
    ]
    if sort_cols:
        return frame.sort_values(sort_cols).reset_index(drop=True)
    return frame.reset_index(drop=True)


def _query_years(start_date: str | None, end_date: str | None) -> set[int]:
    if not start_date and not end_date:
        return set()
    start_year = int((start_date or SUPPORTED_START_DATE)[:4])
    end_year = int((end_date or SUPPORTED_END_DATE)[:4])
    return set(range(start_year, end_year + 1))


def _supported_range_from_coverage(datasets: list[dict[str, Any]]) -> tuple[str, str]:
    by_name = {item.get("dataset"): item for item in datasets}
    core_names = ["prices_1d_pre", "prices_1d_none", "index_prices_1d", "tradability_1d", "valuation_1d"]
    core = [by_name[name] for name in core_names if by_name.get(name, {}).get("min_date") and by_name.get(name, {}).get("max_date")]
    if len(core) < len(core_names):
        return SUPPORTED_START_DATE, SUPPORTED_END_DATE
    starts = [str(item["min_date"]) for item in core]
    ends = [str(item["max_date"]) for item in core]
    return min(starts), min(ends)


def _parse_year(path: Path) -> int | None:
    try:
        return int(path.stem.split("=", 1)[1])
    except Exception:
        return None


def _date_range(frame: pd.DataFrame, date_column: str | None) -> tuple[str | None, str | None]:
    if frame.empty or not date_column or date_column not in frame.columns:
        return None, None
    dates = pd.to_datetime(frame[date_column], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")


def _parquet_rows(path: Path) -> int:
    try:
        return int(pq.ParquetFile(path).metadata.num_rows)
    except Exception:
        try:
            return int(len(pd.read_parquet(path)))
        except Exception:
            return 0


def _min_date(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return min(left, right)


def _max_date(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
