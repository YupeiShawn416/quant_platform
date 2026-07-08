import zipfile

import pandas as pd

from rq_platform.backtest.result_store import BacktestResultStore


def test_result_store_round_trip_and_zip(tmp_path):
    store = BacktestResultStore(root=tmp_path / "runs")
    run_dir = store.create_run_dir("run_001")

    store.write_json(run_dir, "summary.json", {"run_id": "run_001", "total_return": 0.1})
    store.write_csv(run_dir, "nav.csv", pd.DataFrame({"trade_date": ["2025-01-02"], "strategy_nav": [1.0]}))

    assert store.read_json("run_001", "summary.json")["total_return"] == 0.1
    loaded = store.read_csv("run_001", "nav.csv")
    assert loaded.to_dict("records") == [{"trade_date": "2025-01-02", "strategy_nav": 1.0}]

    runs = store.list_runs()
    assert len(runs) == 1
    assert runs[0]["run_id"] == "run_001"

    zip_path = store.package_zip("run_001")
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as archive:
        assert "run_001/summary.json" in archive.namelist()
        assert "run_001/nav.csv" in archive.namelist()


def test_result_store_rejects_path_escape(tmp_path):
    store = BacktestResultStore(root=tmp_path / "runs")

    try:
        store.read_json("../bad", "summary.json")
    except ValueError:
        assert True
    else:
        raise AssertionError("path escape should raise ValueError")
