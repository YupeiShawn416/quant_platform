from __future__ import annotations

from pathlib import Path
from typing import Iterable

from rq_platform.data.parquet_lake import write_by_year
from rq_platform.data_sources.rqdata_source import RQDataSource


def update_daily_prices(
    symbols: Iterable[str],
    start: str,
    end: str,
    adjust_types: Iterable[str],
) -> dict[str, list[Path]]:
    source = RQDataSource()
    outputs: dict[str, list[Path]] = {}
    for adjust_type in adjust_types:
        frame = source.get_daily_prices(symbols, start, end, adjust_type=adjust_type)
        if source.last_price_field_warning:
            print(f"price fields warning ({adjust_type}): {source.last_price_field_warning}")
        paths = write_by_year(
            frame,
            f"prices_1d_{adjust_type}",
            date_col="trade_date",
            dedupe_keys=["trade_date", "order_book_id", "adjust_type"],
        )
        outputs[adjust_type] = paths
        path_text = ", ".join(str(path) for path in paths) or "(no files written)"
        print(f"prices saved: adjust_type={adjust_type} rows={len(frame)} files={path_text}")
    return outputs
