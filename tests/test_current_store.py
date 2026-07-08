import json
import zipfile

import pandas as pd

from rq_platform.backtest.current_store import CurrentBacktestStore


def test_current_store_lifecycle(tmp_path):
    current_dir = tmp_path / "current"
    run_dir = tmp_path / "run_001"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"run_id": "run_001", "total_return": 0.1}),
        encoding="utf-8",
    )
    pd.DataFrame({"trade_date": ["2025-01-02"], "strategy_nav": [1.0]}).to_csv(
        run_dir / "nav.csv", index=False
    )
    (run_dir / "logs.txt").write_text("ok\n", encoding="utf-8")
    (run_dir / ".env").write_text("SECRET=bad\n", encoding="utf-8")

    store = CurrentBacktestStore(current_dir=current_dir)

    assert not store.current_exists()
    store.set_current_from_run_dir(run_dir)
    assert store.current_exists()
    assert store.read_current_json("summary.json")["run_id"] == "run_001"
    assert store.read_current_csv("nav.csv").to_dict("records") == [
        {"trade_date": "2025-01-02", "strategy_nav": 1.0}
    ]
    assert not (current_dir / ".env").exists()

    zip_path = store.package_current_zip()
    assert zip_path.exists()
    with zipfile.ZipFile(zip_path) as archive:
        assert "current/summary.json" in archive.namelist()
        assert "current/nav.csv" in archive.namelist()

    store.delete_current()
    assert not store.current_exists()
