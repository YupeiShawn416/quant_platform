from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file
from rq_platform.data_sources.rqdata_source import DEFAULT_INDUSTRY_SOURCE, RQDataSource
from rq_platform.settings import settings


INDUSTRY_COLUMNS = [
    "trade_date",
    "order_book_id",
    "industry_system",
    "industry_level",
    "industry_code",
    "industry_name",
]


def update_industry_classification(
    year: int = 2025,
    source_name: str = DEFAULT_INDUSTRY_SOURCE,
    level: int = 1,
    max_dates: int | None = None,
    source: RQDataSource | None = None,
) -> dict:
    if year != 2025:
        raise ValueError("This MVP only supports year=2025")
    symbols = _load_a_share_symbols()
    dates = _load_trading_dates(year)
    if max_dates is not None:
        dates = dates[:max_dates]
    data_source = source or RQDataSource()
    frames: list[pd.DataFrame] = []
    print(
        "update industry classification: "
        f"year={year} source={source_name} level={level} symbols={len(symbols)} dates={len(dates)}"
    )
    for trade_date in dates:
        frame = data_source.get_industry_classification(
            symbols,
            trade_date=trade_date,
            source=source_name,
            level=level,
        )
        frames.append(frame)
        print(f"industry date={trade_date} rows={len(frame)}")

    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=INDUSTRY_COLUMNS)
    path = write_industry_classification(output, year=year)
    result = summarize_industry(output, path)
    print_industry_update_summary(result)
    return result


def write_industry_classification(frame: pd.DataFrame, year: int = 2025) -> Path:
    output = _normalize_industry_frame(frame)
    root = settings.data_root_path / "industry_classification"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"year={year}.parquet"
    output.to_parquet(path, index=False)
    return path


def summarize_industry(frame: pd.DataFrame, path: Path) -> dict:
    result = {
        "path": str(path),
        "rows": int(len(frame)),
        "symbols": 0,
        "min_date": None,
        "max_date": None,
        "systems": [],
    }
    if frame.empty:
        return result
    result["symbols"] = int(frame["order_book_id"].nunique())
    result["min_date"] = str(frame["trade_date"].min())
    result["max_date"] = str(frame["trade_date"].max())
    result["systems"] = sorted(frame["industry_system"].dropna().astype(str).unique().tolist())
    return result


def print_industry_update_summary(result: dict) -> None:
    print("industry classification update result")
    for key, value in result.items():
        print(f"  {key}: {value}")


def _normalize_industry_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(frame).copy()
    for column in INDUSTRY_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA
    output = output[INDUSTRY_COLUMNS]
    if output.empty:
        return output
    output["trade_date"] = pd.to_datetime(output["trade_date"]).dt.strftime("%Y-%m-%d")
    output["order_book_id"] = output["order_book_id"].astype(str)
    output["industry_system"] = output["industry_system"].astype(str)
    output["industry_level"] = pd.to_numeric(output["industry_level"], errors="coerce").astype("Int64")
    output["industry_code"] = output["industry_code"].astype("string")
    output["industry_name"] = output["industry_name"].astype("string")
    output = output.drop_duplicates(
        ["trade_date", "order_book_id", "industry_system", "industry_level"], keep="last"
    )
    return output.sort_values(["trade_date", "order_book_id", "industry_system"]).reset_index(drop=True)


def _load_a_share_symbols() -> list[str]:
    instruments = read_single_file("instruments", "instruments.parquet")
    if "order_book_id" not in instruments.columns:
        raise ValueError("instruments 缺少 order_book_id 字段")
    frame = instruments.copy()
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame = frame[frame["order_book_id"].str.endswith((".XSHG", ".XSHE"), na=False)]
    if "status" in frame.columns:
        active = frame[frame["status"].astype(str).str.lower() == "active"]
        if not active.empty:
            frame = active
    return sorted(frame["order_book_id"].dropna().drop_duplicates().tolist())


def _load_trading_dates(year: int) -> list[str]:
    calendar = read_single_file("trading_calendar", "trading_calendar.parquet")
    frame = calendar.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame = frame[pd.to_datetime(frame["trade_date"]).dt.year == year]
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(bool)]
    return frame["trade_date"].drop_duplicates().sort_values().tolist()
