from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file, write_by_year
from rq_platform.data_sources.rqdata_source import RQDataSource
from rq_platform.etl.update_status import append_status, is_batch_done, load_status
from rq_platform.settings import settings


DEDUPE_KEYS = ["trade_date", "order_book_id", "adjust_type"]
STATUS_PATH = settings.data_root_path / "update_logs" / "daily_prices_2025_status.csv"


def update_all_daily_prices(
    start: str,
    end: str,
    year: int,
    adjust_types: list[str],
    batch_size: int = 300,
    resume: bool = True,
    max_batches: int | None = None,
) -> None:
    if year != 2025:
        raise ValueError("This MVP only supports year=2025")
    if start < "2025-01-01" or end > "2025-12-31":
        raise ValueError("This MVP only supports dates within 2025")

    symbols = _load_a_share_symbols()
    batches = _split_batches(symbols, batch_size)
    if max_batches is not None:
        batches = batches[:max_batches]

    status_df = load_status(STATUS_PATH)
    source = RQDataSource()
    print(
        "update 2025 daily prices: "
        f"symbols={len(symbols)} batches={len(batches)} batch_size={batch_size} "
        f"resume={resume} max_batches={max_batches}"
    )

    for adjust_type in adjust_types:
        dataset = f"prices_1d_{adjust_type}"
        for batch_id, batch_symbols in batches:
            if resume and is_batch_done(status_df, adjust_type, year, batch_id):
                print(f"skip done batch: adjust_type={adjust_type} batch_id={batch_id}")
                continue

            try:
                frame = source.get_daily_prices(
                    batch_symbols,
                    start=start,
                    end=end,
                    adjust_type=adjust_type,
                )
                if source.last_price_field_warning:
                    print(f"price fields warning ({adjust_type}): {source.last_price_field_warning}")
                paths = write_by_year(
                    frame,
                    dataset,
                    date_col="trade_date",
                    dedupe_keys=DEDUPE_KEYS,
                )
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                append_status(
                    STATUS_PATH,
                    {
                        "dataset": dataset,
                        "adjust_type": adjust_type,
                        "year": year,
                        "batch_id": batch_id,
                        "start_date": start,
                        "end_date": end,
                        "symbol_count": len(batch_symbols),
                        "status": "failed",
                        "row_count": 0,
                        "output_files": "",
                        "error": error,
                    },
                )
                print(
                    "batch failed: "
                    f"adjust_type={adjust_type} batch_id={batch_id} error={error}"
                )
                if "RQData license 初始化失败" in str(exc):
                    raise
                status_df = load_status(STATUS_PATH)
                continue

            output_files = ";".join(str(path) for path in paths)
            append_status(
                STATUS_PATH,
                {
                    "dataset": dataset,
                    "adjust_type": adjust_type,
                    "year": year,
                    "batch_id": batch_id,
                    "start_date": start,
                    "end_date": end,
                    "symbol_count": len(batch_symbols),
                    "status": "success",
                    "row_count": len(frame),
                    "output_files": output_files,
                    "error": "",
                },
            )
            status_df = load_status(STATUS_PATH)
            print(
                "batch success: "
                f"adjust_type={adjust_type} batch_id={batch_id} "
                f"symbols={len(batch_symbols)} rows={len(frame)} files={output_files}"
            )


def _load_a_share_symbols() -> list[str]:
    try:
        instruments = read_single_file("instruments", "instruments.parquet")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "未找到本地 instruments/instruments.parquet，请先运行 "
            "PYTHONPATH=src python scripts/02_update_small_sample.py"
        ) from exc

    if "order_book_id" not in instruments.columns:
        raise ValueError("instruments 缺少 order_book_id 字段")

    frame = instruments.copy()
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame = frame[
        frame["order_book_id"].str.endswith((".XSHG", ".XSHE"), na=False)
    ]
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


def status_path() -> Path:
    return STATUS_PATH
