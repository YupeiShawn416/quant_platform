from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config
from strategy_research.package_builder import build_strategy_package


config = load_config()
weights = pd.read_csv(Path(config["output"]["root_dir"]) / "weights.csv")
package_path = build_strategy_package(config, weights, config["output"]["package_path"])
print(f"strategy package={package_path}")
