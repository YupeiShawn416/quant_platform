from __future__ import annotations

from pathlib import Path

from rq_platform.backtest.result_store import BacktestResultStore


RUN_ID = "demo_daily_backtest"


def main() -> None:
    run_dir = Path("runs/backtests") / RUN_ID
    if not run_dir.exists():
        print("demo 不存在，请先运行：make demo-daily-backtest")
        return

    store = BacktestResultStore()
    summary = store.read_json(RUN_ID, "summary.json")
    nav = store.read_csv(RUN_ID, "nav.csv")
    trades = store.read_csv(RUN_ID, "trades.csv")
    daily_account = store.read_csv(RUN_ID, "daily_account.csv")
    zip_path = store.package_zip(RUN_ID)

    print("=== summary ===")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("\n=== nav head ===")
    print(nav.head())
    print("\n=== trades head ===")
    print(trades.head())
    print("\n=== daily_account tail ===")
    print(daily_account.tail())
    print(f"\nzip package: {zip_path}")


if __name__ == "__main__":
    main()
