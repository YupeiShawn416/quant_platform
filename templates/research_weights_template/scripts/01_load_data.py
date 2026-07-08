from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config
from strategy_research.data_loader import load_benchmark, load_market_data, load_universe


config = load_config()
output = Path(config["output"]["root_dir"])
output.mkdir(parents=True, exist_ok=True)
market = load_market_data(config)
universe = load_universe(config)
benchmark = load_benchmark(config)
market.to_csv(output / "market_data.csv", index=False)
universe.to_csv(output / "universe.csv", index=False)
benchmark.to_csv(output / "benchmark.csv", index=False)
print(f"market rows={len(market)} path={output / 'market_data.csv'}")
print(f"universe rows={len(universe)} path={output / 'universe.csv'}")
print(f"benchmark rows={len(benchmark)} path={output / 'benchmark.csv'}")
