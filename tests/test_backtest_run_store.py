import json

import pandas as pd

from rq_platform.backtest.run_store import BacktestRunResultNotFound, BacktestRunStore


def test_run_store_saves_reads_zips_and_deletes_cache(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "summary.json").write_text(json.dumps({"run_id": "demo"}), encoding="utf-8")
    pd.DataFrame({"trade_date": ["2025-01-02"], "strategy_nav": [1.0]}).to_csv(
        source / "nav.csv", index=False
    )
    (source / "logs.txt").write_text("ok\n", encoding="utf-8")
    (source / ".env").write_text("secret\n", encoding="utf-8")

    store = BacktestRunStore(tmp_path / "cache")
    cache_dir = store.save_result_to_cache("demo", source)

    assert cache_dir.exists()
    assert not (cache_dir / ".env").exists()
    assert store.read_json("demo", "summary.json")["run_id"] == "demo"
    assert len(store.read_csv("demo", "nav.csv")) == 1
    assert store.read_text("demo", "logs.txt") == "ok\n"
    assert store.package_zip("demo").exists()

    assert store.delete_cache("demo") is True
    assert store.result_available("demo") is False

    try:
        store.read_json("demo", "summary.json")
    except BacktestRunResultNotFound:
        pass
    else:
        raise AssertionError("expected missing run result")
