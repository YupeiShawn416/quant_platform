from __future__ import annotations

from pathlib import Path

from rq_platform.data.parquet_lake import write_single_file
from rq_platform.data_sources.rqdata_source import RQDataSource


def update_calendar(start: str = "2025-01-01", end: str = "2025-12-31") -> Path:
    source = RQDataSource()
    frame = source.get_trading_calendar(start, end)
    path = write_single_file(frame, "trading_calendar", "trading_calendar.parquet")
    print(f"trading calendar saved: {path} rows={len(frame)}")
    return path
