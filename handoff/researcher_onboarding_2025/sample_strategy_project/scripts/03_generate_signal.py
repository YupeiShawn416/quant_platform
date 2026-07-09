from __future__ import annotations

import sys

import pandas as pd

from common import load_config, project_path

sys.path.insert(0, str(project_path("src")))
from strategy_research.signal import factor_to_signal


def main() -> int:
    config = load_config()
    factor_path = project_path(config["output"]["factor_path"])
    if not factor_path.exists():
        print("找不到 factor 文件，请先运行 scripts/02_compute_factor.py。")
        return 1

    factor = pd.read_csv(factor_path)
    signal = factor_to_signal(factor)
    output_path = project_path(config["output"]["signal_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    signal.to_csv(output_path, index=False)
    print(f"saved signal: {output_path} rows={len(signal)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
