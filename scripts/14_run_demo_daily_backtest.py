from __future__ import annotations

from pathlib import Path

from rq_platform.backtest.worker import run_worker


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    result = run_worker(
        config_path=root / "strategies/demo_small_cap/config.json",
        strategy_path=root / "strategies/demo_small_cap/strategy.py",
        output_root=root / "runs/backtests",
    )
    print(f"demo daily backtest created: {result['run_dir']}")
    print(f"zip package created: {result['zip_path']}")


if __name__ == "__main__":
    main()
