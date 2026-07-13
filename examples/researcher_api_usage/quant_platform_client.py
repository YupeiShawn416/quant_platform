from __future__ import annotations

from typing import Iterable

import pandas as pd
import requests


class QuantPlatformClient:
    def __init__(self, base_url: str, api_token: str | None = None, timeout: int = 60):
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

    def list_datasets(self) -> dict:
        return self._get_json("/data/datasets")

    def get_coverage(self) -> dict:
        return self._get_json("/data/coverage")

    def get_schema(self, dataset: str) -> dict:
        return self._get_json(f"/data/schema/{dataset}")

    def query_dataset(
        self,
        dataset: str,
        start_date: str | None = None,
        end_date: str | None = None,
        order_book_ids: str | Iterable[str] | None = None,
        fields: str | Iterable[str] | None = None,
        limit: int = 5000,
        offset: int = 0,
    ) -> pd.DataFrame:
        payload = self._get_json(
            f"/data/query/{dataset}",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "order_book_id": _csv(order_book_ids),
                "fields": _csv(fields),
                "limit": limit,
                "offset": offset,
            },
        )
        return pd.DataFrame(payload.get("records", []))

    def get_prices(
        self,
        start_date: str,
        end_date: str,
        adjust_type: str = "pre",
        order_book_ids: str | Iterable[str] | None = None,
        fields: str | Iterable[str] | None = None,
        limit: int = 50000,
    ) -> pd.DataFrame:
        dataset = "prices_1d_pre" if adjust_type == "pre" else "prices_1d_none"
        return self.query_dataset(dataset, start_date, end_date, order_book_ids, fields, limit)

    def get_index_prices(
        self,
        start_date: str,
        end_date: str,
        index_ids: str | Iterable[str] | None = None,
        fields: str | Iterable[str] | None = None,
        limit: int = 50000,
    ) -> pd.DataFrame:
        return self.query_dataset("index_prices_1d", start_date, end_date, index_ids, fields, limit)

    def get_valuation(
        self,
        start_date: str,
        end_date: str,
        order_book_ids: str | Iterable[str] | None = None,
        fields: str | Iterable[str] | None = None,
        limit: int = 50000,
    ) -> pd.DataFrame:
        return self.query_dataset("valuation_1d", start_date, end_date, order_book_ids, fields, limit)

    def get_tradability(
        self,
        start_date: str,
        end_date: str,
        order_book_ids: str | Iterable[str] | None = None,
        fields: str | Iterable[str] | None = None,
        limit: int = 50000,
    ) -> pd.DataFrame:
        return self.query_dataset("tradability_1d", start_date, end_date, order_book_ids, fields, limit)

    def get_industry(
        self,
        start_date: str,
        end_date: str,
        order_book_ids: str | Iterable[str] | None = None,
        fields: str | Iterable[str] | None = None,
        limit: int = 50000,
    ) -> pd.DataFrame:
        return self.query_dataset("industry_classification", start_date, end_date, order_book_ids, fields, limit)

    def get_index_members(
        self,
        start_date: str,
        end_date: str,
        index_ids: str | Iterable[str] | None = None,
        limit: int = 50000,
    ) -> pd.DataFrame:
        return self.query_dataset("index_components", start_date, end_date, index_ids, None, limit)

    def get_trading_calendar(self, start_date: str, end_date: str) -> pd.DataFrame:
        return self.query_dataset("trading_calendar", start_date, end_date, limit=50000)

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        response = requests.get(
            f"{self.base_url}{path}",
            params=clean_params,
            headers=self._headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _headers(self) -> dict[str, str]:
        return {"X-API-Token": self.api_token} if self.api_token else {}


def _csv(value: str | Iterable[str] | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    return ",".join(str(item) for item in value)
