from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config
from strategy_research.factor import compute_factor


config = load_config()
output = Path(config["output"]["root_dir"])
market = pd.read_csv(output / "market_data.csv")
factor = compute_factor(market, config)
factor.to_csv(output / "factor.csv", index=False)
coverage = factor["factor_value"].notna().mean()
print(f"factor coverage={coverage:.2%} path={output / 'factor.csv'}")
