from pathlib import Path
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factor_research.factor import compute_factor


config = yaml.safe_load(Path("configs/factor.yaml").read_text(encoding="utf-8"))
output = Path(config["output_dir"])
output.mkdir(parents=True, exist_ok=True)
factor = compute_factor(config)
factor.to_csv(output / "factor_long.csv", index=False)
print(f"factor_long rows={len(factor)} path={output / 'factor_long.csv'}")
