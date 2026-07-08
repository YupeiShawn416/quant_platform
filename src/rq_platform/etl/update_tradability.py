from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data.parquet_lake import read_single_file, write_single_file
from rq_platform.settings import settings


TRADABILITY_COLUMNS = [
    "trade_date",
    "order_book_id",
    "is_listed",
    "is_suspended",
    "is_st",
    "can_buy",
    "can_sell",
    "reason",
]


def build_tradability_dataset(
    year: int = 2025,
    adjust_type: str = "pre",
    data_root: Path | None = None,
) -> pd.DataFrame:
    root = Path(data_root) if data_root is not None else settings.data_root_path
    calendar = _read_calendar(root, year)
    instruments = _read_instruments(root)
    prices = _read_prices(root, adjust_type, year)

    universe = _active_universe_by_date(calendar, instruments)
    price_columns = ["trade_date", "order_book_id", "close", "limit_up", "limit_down"]
    available_price_columns = [column for column in price_columns if column in prices.columns]
    frame = universe.merge(
        prices[available_price_columns],
        on=["trade_date", "order_book_id"],
        how="left",
    )
    frame["is_suspended"] = frame["close"].isna()
    frame["is_st"] = frame["special_type"].fillna("").astype(str).str.upper().str.contains("ST")
    frame["can_buy"] = frame["is_listed"] & ~frame["is_suspended"] & ~frame["is_st"]
    frame["can_sell"] = frame["is_listed"] & ~frame["is_suspended"]

    if {"close", "limit_up"}.issubset(frame.columns):
        close = pd.to_numeric(frame["close"], errors="coerce")
        limit_up = pd.to_numeric(frame["limit_up"], errors="coerce")
        at_limit_up = close.notna() & limit_up.notna() & (close >= limit_up)
        frame.loc[at_limit_up, "can_buy"] = False
    if {"close", "limit_down"}.issubset(frame.columns):
        close = pd.to_numeric(frame["close"], errors="coerce")
        limit_down = pd.to_numeric(frame["limit_down"], errors="coerce")
        at_limit_down = close.notna() & limit_down.notna() & (close <= limit_down)
        frame.loc[at_limit_down, "can_sell"] = False

    frame["reason"] = frame.apply(_reason, axis=1)
    return frame[TRADABILITY_COLUMNS].sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)


def update_tradability_dataset(year: int = 2025, adjust_type: str = "pre") -> dict:
    frame = build_tradability_dataset(year=year, adjust_type=adjust_type)
    path = write_single_file(frame, "tradability_1d", f"year={year}.parquet")
    result = summarize_tradability(frame, path)
    print_tradability_update_summary(result)
    return result


def summarize_tradability(frame: pd.DataFrame, path: Path) -> dict:
    result = {
        "path": str(path),
        "rows": int(len(frame)),
        "symbols": 0,
        "min_date": None,
        "max_date": None,
        "cannot_buy": 0,
        "cannot_sell": 0,
    }
    if frame.empty:
        return result
    result["symbols"] = int(frame["order_book_id"].nunique())
    result["min_date"] = str(frame["trade_date"].min())
    result["max_date"] = str(frame["trade_date"].max())
    result["cannot_buy"] = int((~frame["can_buy"]).sum())
    result["cannot_sell"] = int((~frame["can_sell"]).sum())
    return result


def print_tradability_update_summary(result: dict) -> None:
    print("tradability update result")
    for key, value in result.items():
        print(f"  {key}: {value}")


def _read_calendar(root: Path, year: int) -> pd.DataFrame:
    path = root / "trading_calendar" / "trading_calendar.parquet"
    frame = pd.read_parquet(path)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame = frame[pd.to_datetime(frame["trade_date"]).dt.year == year]
    if "is_open" in frame.columns:
        frame = frame[frame["is_open"].astype(bool)]
    return frame[["trade_date"]].drop_duplicates()


def _read_instruments(root: Path) -> pd.DataFrame:
    try:
        frame = pd.read_parquet(root / "instruments" / "instruments.parquet")
    except FileNotFoundError:
        frame = read_single_file("instruments", "instruments.parquet")
    frame = frame.copy()
    required = {"order_book_id", "listed_date", "de_listed_date"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"instruments missing required columns: {sorted(missing)}")
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame["listed_date"] = pd.to_datetime(frame["listed_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    frame["de_listed_date"] = pd.to_datetime(frame["de_listed_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if "special_type" not in frame.columns:
        frame["special_type"] = ""
    return frame[["order_book_id", "listed_date", "de_listed_date", "special_type"]]


def _read_prices(root: Path, adjust_type: str, year: int) -> pd.DataFrame:
    path = root / f"prices_1d_{adjust_type}" / f"year={year}.parquet"
    frame = pd.read_parquet(path)
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    return frame


def _active_universe_by_date(calendar: pd.DataFrame, instruments: pd.DataFrame) -> pd.DataFrame:
    calendar = calendar.copy()
    calendar["_key"] = 1
    instruments = instruments.copy()
    instruments["_key"] = 1
    frame = calendar.merge(instruments, on="_key", how="inner").drop(columns=["_key"])
    listed = frame["listed_date"].isna() | (frame["listed_date"] <= frame["trade_date"])
    delisted = frame["de_listed_date"].isna() | (frame["de_listed_date"] > frame["trade_date"])
    frame["is_listed"] = listed & delisted
    return frame[frame["is_listed"]].reset_index(drop=True)


def _reason(row) -> str:
    reasons = []
    if not bool(row["is_listed"]):
        reasons.append("not_listed")
    if bool(row["is_suspended"]):
        reasons.append("suspended")
    if bool(row["is_st"]):
        reasons.append("st")
    close = row.get("close")
    limit_up = row.get("limit_up")
    limit_down = row.get("limit_down")
    if pd.notna(close) and pd.notna(limit_up) and close >= limit_up:
        reasons.append("limit_up")
    if pd.notna(close) and pd.notna(limit_down) and close <= limit_down:
        reasons.append("limit_down")
    return ";".join(reasons)
