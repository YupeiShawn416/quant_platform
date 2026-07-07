from __future__ import annotations

from pathlib import Path

from rq_platform.data.parquet_lake import write_single_file
from rq_platform.data_sources.rqdata_source import RQDataSource


def update_instruments() -> Path:
    source = RQDataSource()
    frame = source.get_instruments()
    path = write_single_file(frame, "instruments", "instruments.parquet")
    print(f"instruments saved: {path} rows={len(frame)}")
    return path
