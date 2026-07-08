from __future__ import annotations

from pathlib import Path

import yaml


REQUIRED_TOP_LEVEL = ["strategy_id", "strategy_name", "author", "package_version", "mode", "run"]
REQUIRED_RUN_FIELDS = [
    "run_id",
    "start_date",
    "end_date",
    "initial_cash",
    "adjust_type",
    "frequency",
    "commission_rate",
    "tax_rate",
    "slippage_rate",
    "lot_size",
    "price_field",
]


def load_config(path: str = "configs/strategy.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"config file not found: {config_path}")
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        raise ValueError("strategy config must be a YAML object")
    missing = [field for field in REQUIRED_TOP_LEVEL if field not in config]
    if missing:
        raise ValueError(f"missing config fields: {', '.join(missing)}")
    run = config.get("run")
    if not isinstance(run, dict):
        raise ValueError("config.run must be an object")
    missing_run = [field for field in REQUIRED_RUN_FIELDS if field not in run]
    if missing_run:
        raise ValueError(f"missing config.run fields: {', '.join(missing_run)}")
    return config
