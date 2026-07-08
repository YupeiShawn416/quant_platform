from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config
from strategy_research.portfolio import generate_weights


config = load_config()
output = Path(config["output"]["root_dir"])
signal = pd.read_csv(output / "signal.csv")
weights = generate_weights(signal, config)
weights.to_csv(output / "weights.csv", index=False)
try:
    weights.to_parquet(output / "weights.parquet", index=False)
    parquet_path = output / "weights.parquet"
except Exception:
    parquet_path = None
daily_sums = weights.groupby("trade_date")["target_weight"].sum()
print(f"dates={weights['trade_date'].nunique()} symbols={weights['order_book_id'].nunique()} max_daily_weight={daily_sums.max():.6f}")
print(f"weights csv={output / 'weights.csv'}")
if parquet_path:
    print(f"weights parquet={parquet_path}")
