from pathlib import Path
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factor_research.export import to_factor_wide


config = yaml.safe_load(Path("configs/factor.yaml").read_text(encoding="utf-8"))
output = Path(config["output_dir"])
factor_long = pd.read_csv(output / "factor_long.csv")
factor_wide = to_factor_wide(factor_long)
factor_wide.to_csv(output / "factor_wide.csv", index=False)
(output / "factor_report.md").write_text(f"# Factor Report\n\nrows: {len(factor_long)}\n", encoding="utf-8")
print(f"factor_wide path={output / 'factor_wide.csv'}")
