from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.settings import settings


def dataset_dir(dataset_name: str) -> Path:
    path = settings.data_root_path / dataset_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_single_file(df: pd.DataFrame, dataset_name: str, filename: str) -> Path:
    path = dataset_dir(dataset_name) / filename
    frame = _sort_frame(df)
    frame.to_parquet(path, index=False)
    return path


def read_single_file(dataset_name: str, filename: str) -> pd.DataFrame:
    path = dataset_dir(dataset_name) / filename
    return pd.read_parquet(path)


def write_by_year(
    df: pd.DataFrame,
    dataset_name: str,
    date_col: str = "trade_date",
    dedupe_keys: list[str] | None = None,
) -> list[Path]:
    if df.empty:
        return []
    if date_col not in df.columns:
        raise ValueError(f"date_col not found in DataFrame: {date_col}")

    root = dataset_dir(dataset_name)
    frame = df.copy()
    frame[date_col] = pd.to_datetime(frame[date_col]).dt.strftime("%Y-%m-%d")
    frame["_year"] = pd.to_datetime(frame[date_col]).dt.year.astype(str)

    written_paths: list[Path] = []
    for year, year_frame in frame.groupby("_year", sort=True):
        path = root / f"year={year}.parquet"
        output = year_frame.drop(columns=["_year"])
        if path.exists():
            output = pd.concat([pd.read_parquet(path), output], ignore_index=True)
        if dedupe_keys:
            missing_keys = [key for key in dedupe_keys if key not in output.columns]
            if missing_keys:
                raise ValueError(f"dedupe_keys not found in DataFrame: {missing_keys}")
            output = output.drop_duplicates(dedupe_keys, keep="last")
        output = _sort_frame(output)
        output.to_parquet(path, index=False)
        written_paths.append(path)
    return written_paths


def _sort_frame(df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [
        column for column in ["trade_date", "order_book_id", "adjust_type"] if column in df.columns
    ]
    if sort_cols:
        return df.sort_values(sort_cols).reset_index(drop=True)
    return df.reset_index(drop=True)
