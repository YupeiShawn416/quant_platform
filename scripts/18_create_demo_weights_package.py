from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd


PACKAGE_DIR = Path("/tmp/demo_weights_strategy_package")
PACKAGE_ZIP = Path("/tmp/demo_weights_strategy_package.zip")
SYMBOLS = ["000001.XSHE", "600000.XSHG", "000858.XSHE", "600519.XSHG"]


def main() -> None:
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    dates = pd.bdate_range("2025-01-02", "2025-02-28").strftime("%Y-%m-%d")
    weights = pd.DataFrame(
        [
            {"trade_date": trade_date, "order_book_id": symbol, "target_weight": 0.25}
            for trade_date in dates
            for symbol in SYMBOLS
        ]
    )
    manifest = {
        "package_version": "1.0",
        "strategy_id": "demo_weights_q5",
        "strategy_name": "Demo Weights Q5 Long Only",
        "author": "quant_platform",
        "mode": "weights",
        "created_at": "2026-07-08",
        "description": "Demo equal-weight long-only strategy package.",
    }
    config = {
        "run_id": "demo_weights_package",
        "strategy_name": "Demo Weights Q5 Long Only",
        "start_date": "2025-01-02",
        "end_date": "2025-02-28",
        "initial_cash": 1000000,
        "benchmark": "000300.XSHG",
        "adjust_type": "pre",
        "frequency": "daily",
        "commission_rate": 0.0003,
        "tax_rate": 0.001,
        "slippage_rate": 0.0001,
        "lot_size": 100,
        "price_field": "close",
        "mode": "weights",
        "weight_file": "weights.parquet",
        "weight_mode": "daily_target",
        "allow_weight_normalization": False,
    }
    (PACKAGE_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (PACKAGE_DIR / "config.json").write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    weights.to_csv(PACKAGE_DIR / "weights.csv", index=False)
    weights.to_parquet(PACKAGE_DIR / "weights.parquet", index=False)
    (PACKAGE_DIR / "README.md").write_text("Demo weights strategy package.\n", encoding="utf-8")
    with zipfile.ZipFile(PACKAGE_ZIP, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in ["manifest.json", "config.json", "weights.csv", "weights.parquet", "README.md"]:
            archive.write(PACKAGE_DIR / path, arcname=path)
    print(f"demo weights strategy package created: {PACKAGE_ZIP}")


if __name__ == "__main__":
    main()
