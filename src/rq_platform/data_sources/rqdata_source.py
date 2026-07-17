from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd
import rqdatac

from rq_platform.settings import settings


PREFERRED_PRICE_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "total_turnover",
    "limit_up",
    "limit_down",
    "num_trades",
]

CORE_PRICE_FIELDS = ["open", "high", "low", "close", "volume"]
INDEX_PRICE_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "total_turnover",
    "num_trades",
]
RQDATA_INDEX_PRICE_FIELDS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "total_turnover",
]
VALUATION_FACTOR_MAP = {
    "market_cap": "market_cap",
    "float_market_cap": "market_cap_2",
    "pe_ratio": "pe_ratio",
    "pb_ratio": "pb_ratio",
    "ps_ratio": "ps_ratio",
    "pcf_ratio": "pcf_ratio",
}
DEFAULT_INDUSTRY_SOURCE = "citics_2019"
_RQDATA_INITIALIZED = False


@dataclass
class RQDataSource:
    initialized: bool = False
    last_price_fields: list[str] | None = None
    last_price_field_warning: str | None = None

    def init(self) -> None:
        global _RQDATA_INITIALIZED

        if self.initialized:
            return
        if _RQDATA_INITIALIZED:
            self.initialized = True
            return

        if not settings.rqdata_license:
            raise RuntimeError("未找到 RQDATA_LICENSE，请检查项目根目录 .env")

        try:
            # rqdatac 3.5.x does not accept init(license=...) for this license key.
            # The verified license-key login form is username="license" + password=<key>.
            rqdatac.init(username="license", password=settings.rqdata_license)
        except Exception as exc:
            raise RuntimeError(
                f"RQData license 初始化失败：{type(exc).__name__}: {exc}"
            ) from exc

        self.initialized = True
        _RQDATA_INITIALIZED = True

    def info(self):
        self.init()
        return {
            "rqdatac_version": rqdatac.__version__,
            "server": "rqdatad-pro.ricequant.com:16011",
            "initialized": self.initialized,
        }

    def quota(self):
        self.init()
        try:
            return rqdatac.user.get_quota()
        except Exception as exc:
            return {"quota_check_failed": str(exc)}

    def get_trading_calendar(self, start: str, end: str) -> pd.DataFrame:
        self.init()
        dates = rqdatac.get_trading_dates(start, end)
        frame = pd.DataFrame({"trade_date": pd.to_datetime(dates).strftime("%Y-%m-%d")})
        frame["is_open"] = True
        return frame[["trade_date", "is_open"]]

    def get_instruments(self) -> pd.DataFrame:
        self.init()
        frame = rqdatac.all_instruments(type="CS")
        frame = pd.DataFrame(frame)
        preferred = [
            "order_book_id",
            "symbol",
            "abbrev_symbol",
            "round_lot",
            "listed_date",
            "de_listed_date",
            "type",
            "exchange",
            "status",
        ]
        columns = [column for column in preferred if column in frame.columns]
        extras = [column for column in frame.columns if column not in columns]
        frame = frame[columns + extras]
        for column in ["listed_date", "de_listed_date"]:
            if column in frame.columns:
                frame[column] = pd.to_datetime(
                    frame[column], errors="coerce", format="mixed"
                ).dt.strftime("%Y-%m-%d")
        return frame

    def get_daily_prices(
        self,
        order_book_ids: Iterable[str],
        start: str,
        end: str,
        adjust_type: str = "pre",
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        self.init()
        requested_fields = list(fields or PREFERRED_PRICE_FIELDS)
        self.last_price_fields = requested_fields
        self.last_price_field_warning = None

        try:
            raw = self._get_price(order_book_ids, start, end, adjust_type, requested_fields)
        except Exception as exc:
            if fields is not None:
                raise
            self.last_price_field_warning = (
                "requested extended price fields failed; "
                f"falling back to {CORE_PRICE_FIELDS}: {type(exc).__name__}: {exc}"
            )
            requested_fields = CORE_PRICE_FIELDS
            self.last_price_fields = requested_fields
            raw = self._get_price(order_book_ids, start, end, adjust_type, requested_fields)

        frame = self._normalize_price_frame(raw, adjust_type)
        key_cols = ["trade_date", "order_book_id", "adjust_type"]
        price_cols = [column for column in requested_fields if column in frame.columns]
        other_cols = [column for column in frame.columns if column not in key_cols + price_cols]
        frame = frame[key_cols + price_cols + other_cols]
        frame = frame.drop_duplicates(key_cols, keep="last")
        return frame.sort_values(["order_book_id", "trade_date"]).reset_index(drop=True)

    def get_index_prices(
        self,
        index_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self.init()
        raw = rqdatac.get_price(
            list(index_ids),
            start_date=start_date,
            end_date=end_date,
            frequency="1d",
            fields=RQDATA_INDEX_PRICE_FIELDS,
            expect_df=True,
        )
        frame = self._normalize_index_price_frame(raw)
        if frame.empty:
            print(
                "warning: RQData returned empty index prices "
                f"indices={len(index_ids)} start={start_date} end={end_date}"
            )
            return frame

        columns = ["trade_date", "order_book_id"]
        price_columns = [column for column in INDEX_PRICE_FIELDS if column in frame.columns]
        other_columns = [
            column for column in frame.columns if column not in columns + price_columns
        ]
        frame = frame[columns + price_columns + other_columns]
        frame = frame.drop_duplicates(["trade_date", "order_book_id"], keep="last")
        return frame.sort_values(["order_book_id", "trade_date"]).reset_index(drop=True)

    def get_intraday_snapshots(
        self,
        order_book_ids: list[str],
        start_date: str,
        end_date: str,
        snapshot_times: list[str],
    ) -> pd.DataFrame:
        self.init()
        raw = rqdatac.get_price(
            list(order_book_ids),
            start_date=start_date,
            end_date=end_date,
            frequency="1m",
            fields=["close", "volume", "total_turnover"],
            adjust_type="none",
            expect_df=True,
        )
        frame = pd.DataFrame(raw)
        if isinstance(frame.index, pd.MultiIndex) or frame.index.name:
            frame = frame.reset_index()
        if "datetime" not in frame.columns:
            datetime_col = next((column for column in ["date", "time", "trading_datetime"] if column in frame.columns), None)
            if datetime_col:
                frame = frame.rename(columns={datetime_col: "datetime"})
        if "order_book_id" not in frame.columns:
            id_col = next((column for column in ["id", "instrument"] if column in frame.columns), None)
            if id_col:
                frame = frame.rename(columns={id_col: "order_book_id"})
        if "datetime" not in frame.columns or "order_book_id" not in frame.columns:
            return pd.DataFrame(columns=["datetime", "order_book_id", "close", "volume", "total_turnover"])
        frame["datetime"] = pd.to_datetime(frame["datetime"], errors="coerce")
        frame["snapshot_time"] = frame["datetime"].dt.strftime("%H:%M")
        frame = frame[frame["snapshot_time"].isin(snapshot_times)].copy()
        return frame.drop(columns=["snapshot_time"]).reset_index(drop=True)

    def get_valuation_factors(
        self,
        order_book_ids: list[str],
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self.init()
        factor_names = list(VALUATION_FACTOR_MAP.values())
        factor_frame = rqdatac.get_factor(
            list(order_book_ids),
            factor_names,
            start_date=start_date,
            end_date=end_date,
            expect_df=True,
        )
        valuation = self._normalize_valuation_factor_frame(factor_frame)

        turnover_raw = rqdatac.get_turnover_rate(
            list(order_book_ids),
            start_date=start_date,
            end_date=end_date,
            fields="today",
            expect_df=True,
        )
        turnover = self._normalize_turnover_frame(turnover_raw)
        if valuation.empty:
            frame = turnover
        elif turnover.empty:
            frame = valuation
        else:
            frame = valuation.merge(turnover, on=["trade_date", "order_book_id"], how="outer")

        for column in VALUATION_COLUMNS:
            if column not in frame.columns:
                frame[column] = pd.NA
        frame = frame[VALUATION_COLUMNS]
        frame = frame.drop_duplicates(["trade_date", "order_book_id"], keep="last")
        return frame.sort_values(["order_book_id", "trade_date"]).reset_index(drop=True)

    def get_industry_classification(
        self,
        order_book_ids: list[str],
        trade_date: str,
        source: str = DEFAULT_INDUSTRY_SOURCE,
        level: int = 1,
    ) -> pd.DataFrame:
        self.init()
        raw = rqdatac.get_instrument_industry(
            list(order_book_ids),
            source=source,
            level=level,
            date=trade_date,
        )
        frame = self._normalize_industry_frame(raw, trade_date, source, level)
        return frame.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)

    def get_index_components(self, index_id: str, trade_date: str) -> pd.DataFrame:
        self.init()
        raw = rqdatac.index_components(index_id, date=trade_date)
        frame = pd.DataFrame(
            {
                "trade_date": trade_date,
                "index_id": str(index_id),
                "order_book_id": [str(value) for value in (raw or [])],
            }
        )
        return frame[["trade_date", "index_id", "order_book_id"]]

    def get_index_weights(self, index_id: str, trade_date: str) -> pd.DataFrame:
        self.init()
        raw = rqdatac.index_weights(index_id, date=trade_date)
        if raw is None:
            return pd.DataFrame(columns=["trade_date", "index_id", "order_book_id", "weight"])
        frame = pd.Series(raw, name="weight").reset_index()
        frame = frame.rename(columns={frame.columns[0]: "order_book_id"})
        frame["trade_date"] = trade_date
        frame["index_id"] = str(index_id)
        frame["order_book_id"] = frame["order_book_id"].astype(str)
        frame["weight"] = pd.to_numeric(frame["weight"], errors="coerce")
        return frame[["trade_date", "index_id", "order_book_id", "weight"]]

    def _get_price(
        self,
        order_book_ids: Iterable[str],
        start: str,
        end: str,
        adjust_type: str,
        fields: list[str],
    ) -> pd.DataFrame:
        return rqdatac.get_price(
            list(order_book_ids),
            start_date=start,
            end_date=end,
            frequency="1d",
            fields=fields,
            adjust_type=adjust_type,
            expect_df=True,
        )

    def _normalize_price_frame(
        self, raw: pd.DataFrame, adjust_type: str
    ) -> pd.DataFrame:
        frame = pd.DataFrame(raw).copy()
        if frame.empty:
            return pd.DataFrame(columns=["trade_date", "order_book_id", "adjust_type"])

        frame = frame.reset_index()
        rename_map = {
            "date": "trade_date",
            "datetime": "trade_date",
            "trading_date": "trade_date",
            "order_book_ids": "order_book_id",
        }
        frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})

        if "order_book_id" not in frame.columns:
            object_cols = [column for column in frame.columns if "order_book" in column]
            if object_cols:
                frame = frame.rename(columns={object_cols[0]: "order_book_id"})
        if "trade_date" not in frame.columns:
            date_cols = [
                column
                for column in frame.columns
                if "date" in column.lower() or "time" in column.lower()
            ]
            if date_cols:
                frame = frame.rename(columns={date_cols[0]: "trade_date"})

        if "trade_date" not in frame.columns or "order_book_id" not in frame.columns:
            raise RuntimeError(
                "无法标准化 RQData 行情结果，缺少 trade_date 或 order_book_id"
            )

        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame["order_book_id"] = frame["order_book_id"].astype(str)
        frame["adjust_type"] = adjust_type
        return frame

    def _normalize_index_price_frame(self, raw: pd.DataFrame) -> pd.DataFrame:
        frame = pd.DataFrame(raw).copy()
        if frame.empty:
            return pd.DataFrame(columns=["trade_date", "order_book_id", *INDEX_PRICE_FIELDS])

        frame = frame.reset_index()
        rename_map = {
            "date": "trade_date",
            "datetime": "trade_date",
            "trading_date": "trade_date",
            "order_book_ids": "order_book_id",
        }
        frame = frame.rename(columns={k: v for k, v in rename_map.items() if k in frame.columns})

        if "order_book_id" not in frame.columns:
            object_cols = [column for column in frame.columns if "order_book" in column]
            if object_cols:
                frame = frame.rename(columns={object_cols[0]: "order_book_id"})
        if "trade_date" not in frame.columns:
            date_cols = [
                column
                for column in frame.columns
                if "date" in column.lower() or "time" in column.lower()
            ]
            if date_cols:
                frame = frame.rename(columns={date_cols[0]: "trade_date"})

        if "trade_date" not in frame.columns or "order_book_id" not in frame.columns:
            raise RuntimeError(
                "无法标准化 RQData 指数行情结果，缺少 trade_date 或 order_book_id"
            )

        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame["order_book_id"] = frame["order_book_id"].astype(str)
        for column in INDEX_PRICE_FIELDS:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame

    def _normalize_valuation_factor_frame(self, raw: pd.DataFrame | None) -> pd.DataFrame:
        frame = pd.DataFrame() if raw is None else pd.DataFrame(raw).copy()
        if frame.empty:
            return pd.DataFrame(columns=["trade_date", "order_book_id", *VALUATION_FACTOR_MAP])
        frame = frame.reset_index()
        frame = _rename_security_date_columns(frame)
        reverse_map = {source: target for target, source in VALUATION_FACTOR_MAP.items()}
        frame = frame.rename(columns=reverse_map)
        if "trade_date" not in frame.columns or "order_book_id" not in frame.columns:
            raise RuntimeError("无法标准化 RQData 估值因子结果，缺少 trade_date 或 order_book_id")
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame["order_book_id"] = frame["order_book_id"].astype(str)
        for column in VALUATION_FACTOR_MAP:
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame[["trade_date", "order_book_id", *[c for c in VALUATION_FACTOR_MAP if c in frame.columns]]]

    def _normalize_turnover_frame(self, raw: pd.DataFrame | None) -> pd.DataFrame:
        frame = pd.DataFrame() if raw is None else pd.DataFrame(raw).copy()
        if frame.empty:
            return pd.DataFrame(columns=["trade_date", "order_book_id", "turnover_rate"])
        frame = frame.reset_index()
        frame = _rename_security_date_columns(frame)
        if "today" in frame.columns:
            frame = frame.rename(columns={"today": "turnover_rate"})
        if "trade_date" not in frame.columns or "order_book_id" not in frame.columns:
            raise RuntimeError("无法标准化 RQData 换手率结果，缺少 trade_date 或 order_book_id")
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        frame["order_book_id"] = frame["order_book_id"].astype(str)
        if "turnover_rate" in frame.columns:
            frame["turnover_rate"] = pd.to_numeric(frame["turnover_rate"], errors="coerce")
        return frame[["trade_date", "order_book_id", "turnover_rate"]]

    def _normalize_industry_frame(
        self,
        raw: pd.DataFrame | None,
        trade_date: str,
        source: str,
        level: int,
    ) -> pd.DataFrame:
        frame = pd.DataFrame() if raw is None else pd.DataFrame(raw).copy()
        if frame.empty:
            return pd.DataFrame(
                columns=[
                    "trade_date",
                    "order_book_id",
                    "industry_system",
                    "industry_level",
                    "industry_code",
                    "industry_name",
                ]
            )
        frame = frame.reset_index()
        frame = _rename_security_date_columns(frame)
        if "order_book_id" not in frame.columns:
            raise RuntimeError("无法标准化 RQData 行业结果，缺少 order_book_id")
        code_candidates = [
            "first_industry_code",
            "second_industry_code",
            "third_industry_code",
            "index_code",
            "industry_code",
        ]
        name_candidates = [
            "first_industry_name",
            "second_industry_name",
            "third_industry_name",
            "index_name",
            "industry_name",
        ]
        code_col = next((column for column in code_candidates if column in frame.columns), None)
        name_col = next((column for column in name_candidates if column in frame.columns), None)
        output = pd.DataFrame(
            {
                "trade_date": pd.Timestamp(trade_date).strftime("%Y-%m-%d"),
                "order_book_id": frame["order_book_id"].astype(str),
                "industry_system": source,
                "industry_level": int(level),
                "industry_code": frame[code_col].astype(str) if code_col else pd.NA,
                "industry_name": frame[name_col].astype(str) if name_col else pd.NA,
            }
        )
        return output


VALUATION_COLUMNS = [
    "trade_date",
    "order_book_id",
    "market_cap",
    "float_market_cap",
    "pe_ratio",
    "pb_ratio",
    "ps_ratio",
    "pcf_ratio",
    "turnover_rate",
]


def _rename_security_date_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map = {
        "date": "trade_date",
        "datetime": "trade_date",
        "tradedate": "trade_date",
        "trading_date": "trade_date",
        "order_book_ids": "order_book_id",
    }
    frame = frame.rename(columns={key: value for key, value in rename_map.items() if key in frame.columns})
    if "order_book_id" not in frame.columns:
        object_cols = [column for column in frame.columns if "order_book" in column]
        if object_cols:
            frame = frame.rename(columns={object_cols[0]: "order_book_id"})
    if "trade_date" not in frame.columns:
        date_cols = [
            column
            for column in frame.columns
            if "date" in column.lower() or "time" in column.lower()
        ]
        if date_cols:
            frame = frame.rename(columns={date_cols[0]: "trade_date"})
    return frame
