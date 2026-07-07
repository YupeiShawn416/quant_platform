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
