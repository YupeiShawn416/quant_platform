from __future__ import annotations

from rq_platform.research.vix_q5_audit import (
    DEFAULT_LAGGED_PACKAGE,
    build_lagged_weights,
    build_weights_package,
    load_pilot_config,
    load_pilot_weights,
    load_trading_dates,
)


def main() -> None:
    config = load_pilot_config()
    run_config = config["run"]
    trading_dates = load_trading_dates(run_config["start_date"], run_config["end_date"])
    lagged = build_lagged_weights(load_pilot_weights(), trading_dates)
    output = build_weights_package(
        config=config,
        weights=lagged,
        output_path=DEFAULT_LAGGED_PACKAGE,
        run_id=f"{run_config['run_id']}_lagged",
        strategy_name=f"{config['strategy_name']} Lagged",
    )

    print("VIX Q5 lagged package built")
    print(f"rows: {len(lagged)}")
    print(f"dates: {lagged['trade_date'].nunique()}")
    print(f"unique symbols: {lagged['order_book_id'].nunique()}")
    print(f"package: {output}")


if __name__ == "__main__":
    main()
