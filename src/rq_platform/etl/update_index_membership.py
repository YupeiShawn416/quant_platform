from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file
from rq_platform.data_sources.rqdata_source import RQDataSource
from rq_platform.settings import settings


DEFAULT_INDEX_IDS = ["000300.XSHG", "000905.XSHG", "000852.XSHG"]

INDEX_COMPONENT_COLUMNS = ["trade_date", "index_id", "order_book_id"]
INDEX_WEIGHT_COLUMNS = ["trade_date", "index_id", "order_book_id", "weight"]


def update_index_membership(
    year: int = 2025,
    index_ids: list[str] | None = None,
    max_dates: int | None = None,
    source: RQDataSource | None = None,
) -> dict:
    if year != 2025:
        raise ValueError("This MVP only supports year=2025")
    ids = list(index_ids or DEFAULT_INDEX_IDS)
    dates = _load_trading_dates(year)
    if max_dates is not None:
        dates = dates[:max_dates]
    data_source = source or RQDataSource()
    component_frames: list[pd.DataFrame] = []
    weight_frames: list[pd.DataFrame] = []
    print(f"update index membership: year={year} indices={len(ids)} dates={len(dates)}")
    for index_id in ids:
        for trade_date in dates:
            components = data_source.get_index_components(index_id, trade_date)
            weights = data_source.get_index_weights(index_id, trade_date)
            component_frames.append(components)
            weight_frames.append(weights)
            print(
                "index membership "
                f"index_id={index_id} date={trade_date} components={len(components)} weights={len(weights)}"
            )

    components = (
        pd.concat(component_frames, ignore_index=True)
        if component_frames
        else pd.DataFrame(columns=INDEX_COMPONENT_COLUMNS)
    )
    weights = (
        pd.concat(weight_frames, ignore_index=True)
        if weight_frames
        else pd.DataFrame(columns=INDEX_WEIGHT_COLUMNS)
    )
    component_path = write_index_components(components, year=year)
    weight_path = write_index_weights(weights, year=year)
    result = summarize_index_membership(components, weights, component_path, weight_path)
    print_index_membership_update_summary(result)
    return result


def write_index_components(frame: pd.DataFrame, year: int = 2025) -> Path:
    output = _normalize_components(frame)
    root = settings.data_root_path / "index_components"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"year={year}.parquet"
    output.to_parquet(path, index=False)
    return path


def write_index_weights(frame: pd.DataFrame, year: int = 2025) -> Path:
    output = _normalize_weights(frame)
    root = settings.data_root_path / "index_weights"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"year={year}.parquet"
    output.to_parquet(path, index=False)
    return path


def summarize_index_membership(
    components: pd.DataFrame,
    weights: pd.DataFrame,
    component_path: Path,
    weight_path: Path,
) -> dict:
    result = {
        "component_path": str(component_path),
        "weight_path": str(weight_path),
        "component_rows": int(len(components)),
        "weight_rows": int(len(weights)),
        "indices": 0,
        "min_date": None,
        "max_date": None,
    }
    frame = components if not components.empty else weights
    if frame.empty:
        return result
    result["indices"] = int(frame["index_id"].nunique())
    result["min_date"] = str(frame["trade_date"].min())
    result["max_date"] = str(frame["trade_date"].max())
    return result


def print_index_membership_update_summary(result: dict) -> None:
    print("index membership update result")
    for key, value in result.items():
        print(f"  {key}: {value}")


def _normalize_components(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(frame).copy()
    for column in INDEX_COMPONENT_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA
    output = output[INDEX_COMPONENT_COLUMNS]
    if output.empty:
        return output
    output["trade_date"] = pd.to_datetime(output["trade_date"]).dt.strftime("%Y-%m-%d")
    output["index_id"] = output["index_id"].astype(str)
    output["order_book_id"] = output["order_book_id"].astype(str)
    output = output.drop_duplicates(INDEX_COMPONENT_COLUMNS, keep="last")
    return output.sort_values(["trade_date", "index_id", "order_book_id"]).reset_index(drop=True)


def _normalize_weights(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(frame).copy()
    for column in INDEX_WEIGHT_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA
    output = output[INDEX_WEIGHT_COLUMNS]
    if output.empty:
        return output
    output["trade_date"] = pd.to_datetime(output["trade_date"]).dt.strftime("%Y-%m-%d")
    output["index_id"] = output["index_id"].astype(str)
    output["order_book_id"] = output["order_book_id"].astype(str)
    output["weight"] = pd.to_numeric(output["weight"], errors="coerce")
    output = output.drop_duplicates(["trade_date", "index_id", "order_book_id"], keep="last")
    return output.sort_values(["trade_date", "index_id", "order_book_id"]).reset_index(drop=True)


def _load_trading_dates(year: int) -> list[str]:
    calendar = read_single_file("trading_calendar", "trading_calendar.parquet")
    frame = calendar.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame = frame[pd.to_datetime(frame["trade_date"]).dt.year == year]
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(bool)]
    return frame["trade_date"].drop_duplicates().sort_values().tolist()
