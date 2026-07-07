from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd


STATUS_COLUMNS = [
    "dataset",
    "adjust_type",
    "year",
    "batch_id",
    "start_date",
    "end_date",
    "symbol_count",
    "status",
    "row_count",
    "output_files",
    "error",
    "updated_at",
]


def load_status(status_path: Path) -> pd.DataFrame:
    if not status_path.exists():
        return pd.DataFrame(columns=STATUS_COLUMNS)
    return pd.read_csv(status_path)


def append_status(status_path: Path, record: dict) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    row = {column: record.get(column, "") for column in STATUS_COLUMNS}
    row["updated_at"] = row["updated_at"] or datetime.now().isoformat(timespec="seconds")
    frame = pd.DataFrame([row], columns=STATUS_COLUMNS)
    frame.to_csv(status_path, mode="a", header=not status_path.exists(), index=False)


def is_batch_done(
    status_df: pd.DataFrame, adjust_type: str, year: int, batch_id: int
) -> bool:
    if status_df.empty:
        return False
    required = {"adjust_type", "year", "batch_id", "status"}
    if not required.issubset(status_df.columns):
        return False
    matched = status_df[
        (status_df["adjust_type"].astype(str) == str(adjust_type))
        & (status_df["year"].astype(int) == int(year))
        & (status_df["batch_id"].astype(int) == int(batch_id))
        & (status_df["status"].astype(str) == "success")
    ]
    return not matched.empty
