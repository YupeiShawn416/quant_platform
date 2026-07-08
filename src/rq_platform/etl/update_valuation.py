from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file
from rq_platform.data_sources.rqdata_source import RQDataSource, VALUATION_COLUMNS
from rq_platform.settings import settings


def update_valuation_dataset(
    year: int = 2025,
    batch_size: int = 300,
    max_batches: int | None = None,
    source: RQDataSource | None = None,
) -> dict:
    if year != 2025:
        raise ValueError("This MVP only supports year=2025")
    symbols = _load_a_share_symbols()
    batches = _split_batches(symbols, batch_size)
    if max_batches is not None:
        batches = batches[:max_batches]
    windows = _date_windows(year)
    data_source = source or RQDataSource()
    frames: list[pd.DataFrame] = []
    print(
        "update valuation data: "
        f"year={year} symbols={len(symbols)} batches={len(batches)} windows={len(windows)}"
    )

    for batch_id, batch_symbols in batches:
        for start, end in windows:
            frame = data_source.get_valuation_factors(
                batch_symbols,
                start_date=start,
                end_date=end,
            )
            if not frame.empty:
                frames.append(frame)
            print(
                "valuation batch "
                f"batch_id={batch_id} symbols={len(batch_symbols)} start={start} end={end} rows={len(frame)}"
            )

    output = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=VALUATION_COLUMNS)
    path = write_valuation_dataset(output, year=year)
    result = summarize_valuation(output, path)
    print_valuation_update_summary(result)
    return result


def write_valuation_dataset(frame: pd.DataFrame, year: int = 2025) -> Path:
    output = _normalize_valuation_frame(frame)
    root = settings.data_root_path / "valuation_1d"
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"year={year}.parquet"
    output.to_parquet(path, index=False)
    return path


def summarize_valuation(frame: pd.DataFrame, path: Path) -> dict:
    result = {
        "path": str(path),
        "rows": int(len(frame)),
        "symbols": 0,
        "min_date": None,
        "max_date": None,
    }
    if frame.empty:
        return result
    result["symbols"] = int(frame["order_book_id"].nunique())
    result["min_date"] = str(frame["trade_date"].min())
    result["max_date"] = str(frame["trade_date"].max())
    return result


def print_valuation_update_summary(result: dict) -> None:
    print("valuation update result")
    for key, value in result.items():
        print(f"  {key}: {value}")


def _normalize_valuation_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = pd.DataFrame(frame).copy()
    for column in VALUATION_COLUMNS:
        if column not in output.columns:
            output[column] = pd.NA
    output = output[VALUATION_COLUMNS]
    if output.empty:
        return output
    output["trade_date"] = pd.to_datetime(output["trade_date"]).dt.strftime("%Y-%m-%d")
    output["order_book_id"] = output["order_book_id"].astype(str)
    numeric_columns = [column for column in VALUATION_COLUMNS if column not in {"trade_date", "order_book_id"}]
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.drop_duplicates(["trade_date", "order_book_id"], keep="last")
    return output.sort_values(["order_book_id", "trade_date"]).reset_index(drop=True)


def _load_a_share_symbols() -> list[str]:
    try:
        instruments = read_single_file("instruments", "instruments.parquet")
    except FileNotFoundError as exc:
        raise FileNotFoundError("未找到本地 instruments/instruments.parquet") from exc
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


def _split_batches(symbols: list[str], batch_size: int) -> list[tuple[int, list[str]]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    return [
        (batch_id, symbols[start : start + batch_size])
        for batch_id, start in enumerate(range(0, len(symbols), batch_size))
    ]


def _date_windows(year: int) -> list[tuple[str, str]]:
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    windows = []
    current = start
    while current <= end:
        window_end = min(current + timedelta(days=14), end)
        windows.append((current.isoformat(), window_end.isoformat()))
        current = window_end + timedelta(days=1)
    return windows
