from __future__ import annotations

from typing import Any

import pandas as pd
import requests


class QuantPlatformClient:
    def __init__(
        self, base_url: str = "http://127.0.0.1:8000", token: str | None = None
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session = requests.Session()

    def health(self) -> dict:
        return self._get("/health")

    def status(self) -> dict:
        return self._get("/status", auth=True)

    def data_quality(self, year: int = 2025) -> dict:
        return self._get("/data-quality", params={"year": year}, auth=True)

    def get_instruments(self, limit: int = 20) -> pd.DataFrame:
        payload = self._get("/instruments", params={"limit": limit}, auth=True)
        return pd.DataFrame(payload.get("data", []))

    def get_calendar(
        self, start: str | None = None, end: str | None = None
    ) -> pd.DataFrame:
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        payload = self._get("/calendar", params=params, auth=True)
        return pd.DataFrame(payload.get("data", []))

    def get_prices(
        self,
        symbols: list[str],
        start: str,
        end: str,
        adjust_type: str = "pre",
        fields: list[str] | None = None,
    ) -> pd.DataFrame:
        params = {
            "symbols": ",".join(symbols),
            "start": start,
            "end": end,
            "adjust_type": adjust_type,
        }
        if fields:
            params["fields"] = ",".join(fields)
        payload = self._get("/prices", params=params, auth=True)
        return pd.DataFrame(payload.get("data", []))

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> dict:
        headers = {}
        if auth and self.token:
            headers["X-API-Token"] = self.token
        response = self.session.get(
            f"{self.base_url}{path}",
            params=params,
            headers=headers,
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.status_code} {response.text}")
        return response.json()
