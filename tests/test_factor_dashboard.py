from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.factors.factor_analyzer import FactorAnalyzer
from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore
from rq_platform.settings import settings

from factor_test_utils import write_factor_test_lake


def test_factor_dashboard_pages_open(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    factor_root = tmp_path / "factor_library"
    write_factor_test_lake(data_root)
    store = FactorStore(factor_root)
    FactorCalculator(data_root=data_root, store=store).compute(["market_cap"], "2026-05-01", "2026-07-10")
    FactorAnalyzer(data_root=data_root, store=store).analyze("market_cap")
    monkeypatch.setattr(settings, "factor_library_dir", str(factor_root))
    client = TestClient(app)

    list_page = client.get("/ui/factors")
    detail_page = client.get("/ui/factors/market_cap")

    assert list_page.status_code == 200
    assert "因子库" in list_page.text
    assert "market_cap" in list_page.text
    assert detail_page.status_code == 200
    assert "Market Cap" in detail_page.text
    assert "latest_data_date" in list_page.text
    assert "最近可用日" in detail_page.text
