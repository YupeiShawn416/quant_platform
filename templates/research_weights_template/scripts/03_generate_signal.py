from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config
from strategy_research.signal import generate_signal


config = load_config()
output = Path(config["output"]["root_dir"])
factor = pd.read_csv(output / "factor.csv")
signal = generate_signal(factor, config)
signal.to_csv(output / "signal.csv", index=False)
print(f"signal rows={len(signal)} path={output / 'signal.csv'}")
