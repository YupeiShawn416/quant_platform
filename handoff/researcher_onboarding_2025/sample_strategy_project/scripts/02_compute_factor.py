from __future__ import annotations

import sys

import pandas as pd

from common import load_config, project_path

sys.path.insert(0, str(project_path("src")))
from strategy_research.factor import compute_momentum_factor


def main() -> int:
    config = load_config()
    prices_path = project_path(config["output"]["price_path"])
    if not prices_path.exists():
        print("找不到行情文件，请先运行 scripts/01_load_data.py。")
        return 1

    prices = pd.read_csv(prices_path)
    factor = compute_momentum_factor(prices, config["portfolio"]["lookback_days"])
    output_path = project_path(config["output"]["factor_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    factor.to_csv(output_path, index=False)
    print(f"saved factor: {output_path} rows={len(factor)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
