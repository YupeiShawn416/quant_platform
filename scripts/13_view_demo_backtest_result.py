from __future__ import annotations

from pathlib import Path

from rq_platform.backtest.result_store import BacktestResultStore


RUN_ID = "demo_run"


def main() -> None:
    store = BacktestResultStore()
    run_dir = Path("runs/backtests") / RUN_ID
    if not run_dir.exists():
        print("demo 不存在，请先运行：PYTHONPATH=src python scripts/12_create_demo_backtest_result.py")
        return
    summary = store.read_json(RUN_ID, "summary.json")
    nav = store.read_csv(RUN_ID, "nav.csv")
    trades = store.read_csv(RUN_ID, "trades.csv")
    zip_path = store.package_zip(RUN_ID)

    print("=== summary ===")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("\n=== nav head ===")
    print(nav.head())
    print("\n=== trades head ===")
    print(trades.head())
    print(f"\nzip package: {zip_path}")


if __name__ == "__main__":
    main()
