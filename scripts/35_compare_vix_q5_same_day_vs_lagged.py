from __future__ import annotations

from pathlib import Path

from rq_platform.backtest.package_job_manager import StrategyPackageJobManager
from rq_platform.research.vix_q5_audit import (
    DEFAULT_LAGGED_PACKAGE,
    DEFAULT_SAME_DAY_PACKAGE,
    build_lagged_weights,
    build_weights_package,
    compare_summaries,
    load_pilot_config,
    load_pilot_weights,
    load_trading_dates,
    render_comparison_markdown,
)


OUTPUT_PATH = Path("docs/VIX_Q5_LAGGED_COMPARISON.md")


def main() -> None:
    config = load_pilot_config()
    run_config = config["run"]
    weights = load_pilot_weights()
    trading_dates = load_trading_dates(run_config["start_date"], run_config["end_date"])
    lagged = build_lagged_weights(weights, trading_dates)

    same_day_package = build_weights_package(
        config=config,
        weights=weights,
        output_path=DEFAULT_SAME_DAY_PACKAGE,
        run_id=run_config["run_id"],
        strategy_name=config["strategy_name"],
    )
    lagged_package = build_weights_package(
        config=config,
        weights=lagged,
        output_path=DEFAULT_LAGGED_PACKAGE,
        run_id=f"{run_config['run_id']}_lagged",
        strategy_name=f"{config['strategy_name']} Lagged",
    )

    manager = StrategyPackageJobManager()
    same_day_result = manager.run_package(same_day_package)
    lagged_result = manager.run_package(lagged_package)
    if same_day_result["status"] != "success":
        raise RuntimeError(f"same-day run failed: {same_day_result.get('error')}")
    if lagged_result["status"] != "success":
        raise RuntimeError(f"lagged run failed: {lagged_result.get('error')}")

    same_day_summary = same_day_result["summary"]
    lagged_summary = lagged_result["summary"]
    comparison = compare_summaries(same_day_summary, lagged_summary)
    OUTPUT_PATH.write_text(
        render_comparison_markdown(comparison, same_day_summary, lagged_summary),
        encoding="utf-8",
    )

    print("VIX Q5 same-day vs lagged comparison complete")
    print(f"same-day run_id: {same_day_summary.get('run_id')}")
    print(f"lagged run_id: {lagged_summary.get('run_id')}")
    print(f"same-day total_return: {same_day_summary.get('total_return')}")
    print(f"lagged total_return: {lagged_summary.get('total_return')}")
    print(f"same-day sharpe: {same_day_summary.get('sharpe')}")
    print(f"lagged sharpe: {lagged_summary.get('sharpe')}")
    print(f"report: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
