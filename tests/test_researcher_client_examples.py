import importlib.util
from pathlib import Path

import pandas as pd


def test_quant_platform_client_builds_urls_and_returns_dataframe(monkeypatch):
    module = _load_client_module()
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"records": [{"trade_date": "2025-01-02", "order_book_id": "000001.XSHE", "close": 10.0}]}

    def fake_get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setattr(module.requests, "get", fake_get)
    client = module.QuantPlatformClient("http://server.example/", "secret-token")

    frame = client.get_prices(
        "2025-01-02",
        "2025-01-03",
        order_book_ids=["000001.XSHE"],
        fields=["trade_date", "order_book_id", "close"],
    )

    assert isinstance(frame, pd.DataFrame)
    assert frame.iloc[0]["close"] == 10.0
    assert calls[0]["url"] == "http://server.example/data/query/prices_1d_pre"
    assert calls[0]["headers"] == {"X-API-Token": "secret-token"}
    assert calls[0]["params"]["order_book_id"] == "000001.XSHE"
    assert calls[0]["params"]["fields"] == "trade_date,order_book_id,close"


def _load_client_module():
    path = Path("examples/researcher_api_usage/quant_platform_client.py").resolve()
    spec = importlib.util.spec_from_file_location("quant_platform_client_example", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module
