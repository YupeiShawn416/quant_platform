from fastapi.testclient import TestClient

from rq_platform.api.main import app
from rq_platform.factors.factor_analyzer import FactorAnalyzer
from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_store import FactorStore
from rq_platform.settings import settings

from factor_test_utils import write_factor_test_lake


def test_factor_api_lists_details_and_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "factor_library_dir", str(tmp_path / "factor_library"))
    monkeypatch.setattr(settings, "factor_weights_dir", str(tmp_path / "factor_weights"))
    monkeypatch.setattr(settings, "api_token", "change_me")
    client = TestClient(app)

    response = client.get("/factors")
    assert response.status_code == 200
    assert response.json()["count"] == 5
    assert client.get("/factors/market_cap").status_code == 200
    missing = client.get("/factors/market_cap/ic")
    assert missing.status_code == 404
    assert "run factor analysis first" in missing.text


def test_factor_api_returns_analysis_and_generates_weights(tmp_path, monkeypatch):
    data_root = tmp_path / "data"
    factor_root = tmp_path / "factor_library"
    write_factor_test_lake(data_root)
    store = FactorStore(factor_root)
    FactorCalculator(data_root=data_root, store=store).compute(["momentum_20d"], "2026-05-01", "2026-07-10")
    FactorAnalyzer(data_root=data_root, store=store).analyze("momentum_20d")
    monkeypatch.setattr(settings, "factor_library_dir", str(factor_root))
    monkeypatch.setattr(settings, "factor_weights_dir", str(tmp_path / "factor_weights"))
    monkeypatch.setattr(settings, "api_token", "change_me")
    client = TestClient(app)

    assert client.get("/factors/momentum_20d/ic").json()["count"] > 0
    generated = client.post("/factors/momentum_20d/generate-weights", json={"top_quantile": 0.5, "max_names": 3})

    assert generated.status_code == 200
    assert generated.json()["row_count"] > 0
    assert not generated.json()["target_weights"].startswith("/")

