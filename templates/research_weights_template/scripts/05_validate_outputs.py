from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from strategy_research.config import load_config
from strategy_research.validators import validate_factor_df, validate_signal_df, validate_weights_df


config = load_config()
output = Path(config["output"]["root_dir"])
checks = {
    "factor": validate_factor_df(pd.read_csv(output / "factor.csv")),
    "signal": validate_signal_df(pd.read_csv(output / "signal.csv")),
    "weights": validate_weights_df(pd.read_csv(output / "weights.csv")),
}
lines = ["# Validation Report", ""]
has_error = False
for name, messages in checks.items():
    lines.append(f"## {name}")
    if not messages:
        lines.append("- OK")
    for message in messages:
        lines.append(f"- {message}")
        has_error = has_error or message.startswith("ERROR:")
    lines.append("")
report = output / "validation_report.md"
report.write_text("\n".join(lines), encoding="utf-8")
print(f"validation report={report}")
if has_error:
    raise SystemExit(1)
