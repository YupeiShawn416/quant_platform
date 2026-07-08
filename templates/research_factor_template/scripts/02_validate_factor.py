from pathlib import Path
import sys

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from factor_research.validators import validate_factor_long


config = yaml.safe_load(Path("configs/factor.yaml").read_text(encoding="utf-8"))
factor = pd.read_csv(Path(config["output_dir"]) / "factor_long.csv")
messages = validate_factor_long(factor)
print("\n".join(messages or ["OK"]))
if any(message.startswith("ERROR:") for message in messages):
    raise SystemExit(1)
