import pandas as pd
import pytest

from rq_platform.client import QuantPlatformClient


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_client_can_be_constructed():
    client = QuantPlatformClient(base_url="http://example.test", token=None)

    assert client.base_url == "http://example.test"
    assert client.token is None


def test_get_prices_serializes_symbols_and_fields(monkeypatch):
    calls = []

    def fake_get(self, url, params=None, headers=None, timeout=None):
        calls.append(
            {
                "url": url,
                "params": params,
                "headers": headers,
                "timeout": timeout,
            }
        )
        return FakeResponse(
            payload={
                "data": [
                    {
                        "trade_date": "2025-01-02",
                        "order_book_id": "000001.XSHE",
                        "open": 1.0,
                        "close": 2.0,
                    }
                ]
            }
        )

    monkeypatch.setattr("requests.Session.get", fake_get)
    client = QuantPlatformClient(base_url="http://example.test/", token="secret")

    frame = client.get_prices(
        symbols=["000001.XSHE", "600519.XSHG"],
        start="2025-01-02",
        end="2025-01-10",
        adjust_type="pre",
        fields=["open", "close"],
    )

    assert isinstance(frame, pd.DataFrame)
    assert frame.shape == (1, 4)
    assert calls[0]["url"] == "http://example.test/prices"
    assert calls[0]["params"]["symbols"] == "000001.XSHE,600519.XSHG"
    assert calls[0]["params"]["fields"] == "open,close"
    assert calls[0]["headers"] == {"X-API-Token": "secret"}


def test_health_does_not_send_auth_header(monkeypatch):
    calls = []

    def fake_get(self, url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers})
        return FakeResponse(payload={"status": "ok"})

    monkeypatch.setattr("requests.Session.get", fake_get)
    client = QuantPlatformClient(base_url="http://example.test", token="secret")

    assert client.health() == {"status": "ok"}
    assert calls[0]["headers"] == {}


def test_http_error_raises_runtime_error(monkeypatch):
    def fake_get(self, url, params=None, headers=None, timeout=None):
        return FakeResponse(status_code=500, text="boom")

    monkeypatch.setattr("requests.Session.get", fake_get)
    client = QuantPlatformClient(base_url="http://example.test")

    with pytest.raises(RuntimeError, match="API request failed: 500 boom"):
        client.status()
