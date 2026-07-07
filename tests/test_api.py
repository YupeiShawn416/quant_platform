from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.settings import settings


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "quant_platform_data_api",
    }


def test_prices_missing_required_params_returns_422():
    response = client.get("/prices")

    assert response.status_code == 422


def test_prices_bad_adjust_type_returns_400():
    response = client.get(
        "/prices",
        params={
            "symbols": "000001.XSHE",
            "start": "2025-01-02",
            "end": "2025-01-10",
            "adjust_type": "bad",
        },
    )

    assert response.status_code == 400
    assert "adjust_type" in response.json()["detail"]


def test_prices_rejects_too_many_symbols():
    symbols = ",".join(f"{idx:06d}.XSHE" for idx in range(201))
    response = client.get(
        "/prices",
        params={
            "symbols": symbols,
            "start": "2025-01-02",
            "end": "2025-01-10",
            "adjust_type": "pre",
        },
    )

    assert response.status_code == 400


def test_status_does_not_crash_when_local_files_are_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_root", str(tmp_path))

    response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["data_root"] == str(tmp_path)
    assert not payload["datasets"]["instruments"]["exists"]
    assert payload["datasets"]["instruments"]["rows"] == 0
