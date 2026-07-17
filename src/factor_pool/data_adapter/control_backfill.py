from __future__ import annotations

import shutil
import uuid
from datetime import date
from pathlib import Path
from typing import Iterable, Protocol

import pandas as pd

from factor_pool.data_adapter.rqdata import resolve_credential


class ControlProvider(Protocol):
    def trading_date(self, quarter_end: str) -> str: ...
    def components(self, date: str) -> list[str]: ...
    def industry(self, ids: list[str], date: str) -> pd.DataFrame: ...
    def valuation(self, ids: list[str], date: str) -> pd.DataFrame: ...
    def statuses(self, ids: list[str], date: str) -> pd.DataFrame: ...
    def listing(self, ids: list[str], date: str) -> pd.DataFrame: ...


class RQDataControlProvider:
    def __init__(self) -> None:
        import rqdatac

        credential = resolve_credential()
        rqdatac.init(username="license", password=credential.secret, lazy=False)
        self.sdk = rqdatac

    def trading_date(self, quarter_end: str) -> str:
        end = pd.Timestamp(quarter_end)
        start = end.replace(day=1)
        dates = self.sdk.get_trading_dates(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        if not dates:
            raise ValueError(f"no trading date in quarter-end month: {quarter_end}")
        return pd.Timestamp(dates[-1]).strftime("%Y-%m-%d")

    def components(self, date: str) -> list[str]:
        return sorted(str(value) for value in self.sdk.index_components("000905.XSHG", date=date))

    def industry(self, ids: list[str], date: str) -> pd.DataFrame:
        raw = pd.DataFrame(self.sdk.get_instrument_industry(ids, source="citics_2019", level=1, date=date))
        raw = raw.rename(columns={"first_industry_code": "industry_code", "first_industry_name": "industry_name"})
        raw.index.name = "order_book_id"
        return raw.reset_index()[["order_book_id", "industry_code", "industry_name"]]

    def valuation(self, ids: list[str], date: str) -> pd.DataFrame:
        raw = pd.DataFrame(self.sdk.get_factor(ids, ["market_cap_2"], start_date=date, end_date=date, expect_df=True))
        raw = raw.reset_index().rename(columns={"market_cap_2": "float_market_cap"})
        return raw[["order_book_id", "float_market_cap"]]

    def statuses(self, ids: list[str], date: str) -> pd.DataFrame:
        st = _wide_boolean(self.sdk.is_st_stock(ids, start_date=date, end_date=date), "is_st")
        suspended = _wide_boolean(self.sdk.is_suspended(ids, start_date=date, end_date=date), "is_suspended")
        price = pd.DataFrame(self.sdk.get_price(
            ids,
            start_date=date,
            end_date=date,
            fields=["close", "limit_up", "limit_down"],
            adjust_type="none",
        )).reset_index()
        if "date" in price.columns:
            price = price.drop(columns=["date"])
        return st.merge(suspended, on="order_book_id", how="outer").merge(price, on="order_book_id", how="outer")

    def listing(self, ids: list[str], date: str) -> pd.DataFrame:
        signal_date = pd.Timestamp(date)
        rows = []
        for instrument in self.sdk.instruments(ids):
            listed_date = pd.to_datetime(instrument.listed_date, errors="coerce")
            de_listed_date = pd.to_datetime(instrument.de_listed_date, errors="coerce")
            is_listed = pd.notna(listed_date) and listed_date <= signal_date
            if pd.notna(de_listed_date):
                is_listed = is_listed and signal_date <= de_listed_date
            rows.append({
                "order_book_id": str(instrument.order_book_id),
                "is_listed": bool(is_listed),
                "listed_days": int((signal_date - listed_date).days) if is_listed else None,
            })
        return pd.DataFrame(rows)


def build_quarter_control_frame(
    provider: ControlProvider,
    quarter_end: str,
    *,
    minimum_components: int = 450,
    maximum_components: int = 550,
) -> pd.DataFrame:
    signal_date = provider.trading_date(quarter_end)
    ids = provider.components(signal_date)
    if not ids:
        raise ValueError(f"CSI500 components are empty on {signal_date}")
    base = pd.DataFrame({"order_book_id": ids})
    frame = base.merge(provider.industry(ids, signal_date), on="order_book_id", how="left")
    frame = frame.merge(provider.valuation(ids, signal_date), on="order_book_id", how="left")
    frame = frame.merge(provider.statuses(ids, signal_date), on="order_book_id", how="left")
    frame = frame.merge(provider.listing(ids, signal_date), on="order_book_id", how="left")
    frame["signal_date"] = signal_date
    frame["universe_member"] = True
    frame["is_st"] = frame["is_st"].fillna(False).astype(bool)
    frame["is_suspended"] = frame["is_suspended"].fillna(False).astype(bool)
    frame["is_limit_up"] = frame["close"].notna() & frame["limit_up"].notna() & (frame["close"] >= frame["limit_up"])
    frame["is_limit_down"] = frame["close"].notna() & frame["limit_down"].notna() & (frame["close"] <= frame["limit_down"])
    if frame["order_book_id"].duplicated().any():
        raise ValueError(f"duplicate CSI500 controls on {signal_date}")
    if len(frame) < minimum_components or len(frame) > maximum_components:
        raise ValueError(f"unexpected CSI500 component count on {signal_date}: {len(frame)}")
    return frame.sort_values("order_book_id").reset_index(drop=True)


def backfill_quarterly_controls(
    provider: ControlProvider,
    *,
    quarter_ends: Iterable[str],
    output_root: Path,
    minimum_components: int = 450,
    maximum_components: int = 550,
) -> dict[str, int]:
    output_root.mkdir(parents=True, exist_ok=True)
    result = {"written": 0, "cached": 0, "failed": 0, "rows": 0}
    for quarter_end in quarter_ends:
        signal_date = provider.trading_date(quarter_end)
        final_dir = output_root / f"date={signal_date}"
        final_file = final_dir / "controls.parquet"
        if final_file.is_file():
            result["cached"] += 1
            result["rows"] += len(pd.read_parquet(final_file))
            continue
        temp_dir = output_root / f".date={signal_date}.tmp-{uuid.uuid4().hex}"
        try:
            frame = build_quarter_control_frame(
                provider,
                quarter_end,
                minimum_components=minimum_components,
                maximum_components=maximum_components,
            )
            temp_dir.mkdir()
            frame.to_parquet(temp_dir / "controls.parquet", index=False)
            if len(pd.read_parquet(temp_dir / "controls.parquet")) != len(frame):
                raise ValueError("persisted control row count mismatch")
            temp_dir.replace(final_dir)
            result["written"] += 1
            result["rows"] += len(frame)
        except Exception:
            result["failed"] += 1
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise
    return result


def generate_quarter_ends(start: str, end: str) -> list[str]:
    periods = pd.period_range(pd.Timestamp(start), pd.Timestamp(end), freq="Q")
    return [period.end_time.strftime("%Y-%m-%d") for period in periods if period.end_time.date() <= pd.Timestamp(end).date()]


def _wide_boolean(raw, name: str) -> pd.DataFrame:
    frame = pd.DataFrame(raw)
    if frame.empty:
        return pd.DataFrame({"order_book_id": [], name: []})
    series = frame.iloc[-1].rename(name)
    series.index.name = "order_book_id"
    return series.reset_index()
