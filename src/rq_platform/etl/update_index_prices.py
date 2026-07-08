from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data.parquet_lake import dataset_dir
from rq_platform.data_sources.rqdata_source import RQDataSource


DEFAULT_INDEX_IDS = [
    "000300.XSHG",
    "000905.XSHG",
    "000852.XSHG",
    "000001.XSHG",
    "399001.XSHE",
    "399006.XSHE",
]

INDEX_PRICE_COLUMNS = [
    "trade_date",
    "order_book_id",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "total_turnover",
    "num_trades",
]


def update_index_prices(
    year: int = 2025,
    index_ids: list[str] | None = None,
    source: RQDataSource | None = None,
) -> dict:
    if year != 2025:
        raise ValueError("This MVP only supports year=2025")

    ids = list(index_ids or DEFAULT_INDEX_IDS)
    start = f"{year}-01-01"
    end = f"{year}-12-31"
    data_source = source or RQDataSource()
    frame = data_source.get_index_prices(ids, start_date=start, end_date=end)
    output_path = write_index_prices(frame, year=year)
    result = summarize_index_prices(frame, output_path)
    print_index_update_summary(result)
    return result


def write_index_prices(frame: pd.DataFrame, year: int = 2025) -> Path:
    output = _normalize_index_frame(frame)
    root = dataset_dir("index_prices_1d")
    path = root / f"year={year}.parquet"
    output.to_parquet(path, index=False)
    return path


def summarize_index_prices(frame: pd.DataFrame, output_path: Path) -> dict:
    result = {
        "path": str(output_path),
        "rows": int(len(frame)),
        "indices": 0,
        "min_date": None,
        "max_date": None,
    }
    if frame.empty:
        return result
    result["indices"] = int(frame["order_book_id"].nunique())
    result["min_date"] = str(frame["trade_date"].min())
    result["max_date"] = str(frame["trade_date"].max())
    return result


def print_index_update_summary(result: dict) -> None:
    print("index prices update result")
    for key, value in result.items():
        print(f"  {key}: {value}")


def _normalize_index_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(frame).copy()
    for column in INDEX_PRICE_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA
    output = output[INDEX_PRICE_COLUMNS]
    if output.empty:
        return output
    output["trade_date"] = pd.to_datetime(output["trade_date"]).dt.strftime("%Y-%m-%d")
    output["order_book_id"] = output["order_book_id"].astype(str)
    numeric_columns = [column for column in INDEX_PRICE_COLUMNS if column not in {"trade_date", "order_book_id"}]
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.drop_duplicates(["trade_date", "order_book_id"], keep="last")
    return output.sort_values(["order_book_id", "trade_date"]).reset_index(drop=True)
