import zipfile

import pandas as pd

from strategy_research.package_builder import build_strategy_package


def test_build_strategy_package_contains_standard_files(tmp_path):
    config = {
        "strategy_id": "demo_weights_template",
        "strategy_name": "Demo",
        "author": "tester",
        "package_version": "1.0",
        "description": "",
        "run": {
            "run_id": "demo",
            "start_date": "2025-01-02",
            "end_date": "2025-01-03",
            "initial_cash": 100000,
            "adjust_type": "pre",
            "frequency": "daily",
            "commission_rate": 0.0003,
            "tax_rate": 0.001,
            "slippage_rate": 0.0001,
            "lot_size": 100,
            "price_field": "close",
        },
    }
    weights = pd.DataFrame({"trade_date": ["2025-01-02"], "order_book_id": ["AAA.X"], "target_weight": [1.0]})
    package = build_strategy_package(config, weights, tmp_path / "package.zip")
    with zipfile.ZipFile(package) as archive:
        names = set(archive.namelist())
    assert {"manifest.json", "config.json", "weights.csv", "README.md"}.issubset(names)
