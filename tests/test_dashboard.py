from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.settings import settings


client = TestClient(app)


def test_ui_redirects(monkeypatch, tmp_path):
    _patch_empty_current(monkeypatch, tmp_path)

    response = client.get("/ui", follow_redirects=False)

    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/ui/backtests/current"


def test_current_dashboard_empty_state(monkeypatch, tmp_path):
    _patch_empty_current(monkeypatch, tmp_path)

    response = client.get("/ui/backtests/current")

    assert response.status_code == 200
    assert "当前没有回测结果" in response.text


def test_current_dashboard_pages_do_not_crash(monkeypatch, tmp_path):
    _patch_empty_current(monkeypatch, tmp_path)

    for path in [
        "/ui/backtests/current/trades",
        "/ui/backtests/current/logs",
        "/ui/backtests/current/nav",
    ]:
        response = client.get(path)
        assert response.status_code == 200
        assert "Backtest Dashboard" in response.text


def test_data_dashboard_page_opens(monkeypatch, tmp_path):
    _patch_empty_current(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "data_root", str(tmp_path / "rqdata"))

    response = client.get("/ui/data")

    assert response.status_code == 200
    assert "研究员数据" in response.text
    assert "prices_1d_pre" in response.text


def _patch_empty_current(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "api_token", "change_me")
    monkeypatch.setattr(settings, "backtest_current_dir", str(tmp_path / "missing_current"))
