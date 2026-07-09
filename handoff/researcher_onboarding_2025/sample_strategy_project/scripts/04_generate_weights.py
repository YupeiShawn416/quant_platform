from __future__ import annotations

import sys

import pandas as pd

from common import load_config, project_path

sys.path.insert(0, str(project_path("src")))
from strategy_research.portfolio import build_equal_weight_portfolio


def main() -> int:
    config = load_config()
    signal_path = project_path(config["output"]["signal_path"])
    if not signal_path.exists():
        print("找不到 signal 文件，请先运行 scripts/03_generate_signal.py。")
        return 1

    signal = pd.read_csv(signal_path)
    weights = build_equal_weight_portfolio(signal, config["portfolio"]["top_n"])
    if weights.empty:
        print("没有生成任何权重，请检查因子是否全为空。")
        return 1

    output_path = project_path(config["output"]["weights_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    weights.to_csv(output_path, index=False)
    print(f"saved weights: {output_path} rows={len(weights)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
