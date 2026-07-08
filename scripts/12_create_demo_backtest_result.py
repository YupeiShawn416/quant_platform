from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from rq_platform.backtest.result_schema import (
    DAILY_ACCOUNT_COLUMNS,
    NAV_COLUMNS,
    ORDERS_COLUMNS,
    POSITIONS_COLUMNS,
    SUMMARY_FIELDS,
    TRADES_COLUMNS,
)
from rq_platform.backtest.result_store import BacktestResultStore
from rq_platform.metrics import calculate_performance_metrics


RUN_ID = "demo_run"
STRATEGY_NAME = "demo_small_cap"
INITIAL_CASH = 1_000_000
START = "2025-01-02"
END = "2025-02-28"


def main() -> None:
    store = BacktestResultStore()
    run_dir = store.create_run_dir(RUN_ID)
    frames = _build_demo_frames()
    metrics = calculate_performance_metrics(frames["nav"])
    final_value = float(frames["daily_account"]["total_value"].iloc[-1])
    created_at = datetime.now().isoformat(timespec="seconds")

    summary = {
        "run_id": RUN_ID,
        "strategy_name": STRATEGY_NAME,
        "start_date": START,
        "end_date": END,
        "initial_cash": INITIAL_CASH,
        "final_value": final_value,
        "trade_count": int(len(frames["trades"])),
        "created_at": created_at,
        **metrics,
    }
    summary = {field: summary.get(field) for field in SUMMARY_FIELDS}
    manifest = {
        "run_id": RUN_ID,
        "strategy_name": STRATEGY_NAME,
        "created_at": created_at,
        "files": [
            "manifest.json",
            "config.json",
            "summary.json",
            "summary.csv",
            "nav.csv",
            "daily_account.csv",
            "positions.csv",
            "trades.csv",
            "orders.csv",
            "logs.txt",
            "monthly_returns.csv",
            "rolling_metrics.csv",
            "charts.json",
        ],
    }
    config = {
        "run_id": RUN_ID,
        "strategy_name": STRATEGY_NAME,
        "initial_cash": INITIAL_CASH,
        "start_date": START,
        "end_date": END,
        "benchmark": "000300.XSHG",
        "engine": "demo",
    }
    charts = {
        "nav": frames["nav"][["trade_date", "strategy_nav", "benchmark_nav", "excess_nav"]].to_dict("records"),
        "drawdown": frames["nav"][["trade_date", "drawdown"]].to_dict("records"),
    }

    store.write_json(run_dir, "manifest.json", manifest)
    store.write_json(run_dir, "config.json", config)
    store.write_json(run_dir, "summary.json", summary)
    store.write_csv(run_dir, "summary.csv", pd.DataFrame([summary], columns=SUMMARY_FIELDS))
    store.write_csv(run_dir, "nav.csv", frames["nav"][NAV_COLUMNS])
    store.write_csv(run_dir, "daily_account.csv", frames["daily_account"][DAILY_ACCOUNT_COLUMNS])
    store.write_csv(run_dir, "positions.csv", frames["positions"][POSITIONS_COLUMNS])
    store.write_csv(run_dir, "trades.csv", frames["trades"][TRADES_COLUMNS])
    store.write_csv(run_dir, "orders.csv", frames["orders"][ORDERS_COLUMNS])
    store.write_csv(run_dir, "monthly_returns.csv", frames["monthly_returns"])
    store.write_csv(run_dir, "rolling_metrics.csv", frames["rolling_metrics"])
    store.write_json(run_dir, "charts.json", charts)
    (run_dir / "logs.txt").write_text(
        "\n".join(
            [
                "demo backtest result created",
                f"run_id={RUN_ID}",
                f"strategy_name={STRATEGY_NAME}",
                "no real strategy engine executed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    zip_path = store.package_zip(RUN_ID)
    print(f"demo backtest result created: {run_dir}")
    print(f"zip package created: {zip_path}")


def _build_demo_frames() -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(42)
    dates = pd.bdate_range(START, END)
    trade_dates = dates.strftime("%Y-%m-%d")
    strategy_returns = rng.normal(0.0012, 0.012, len(dates))
    benchmark_returns = rng.normal(0.0007, 0.009, len(dates))
    strategy_nav = (1 + pd.Series(strategy_returns)).cumprod()
    benchmark_nav = (1 + pd.Series(benchmark_returns)).cumprod()
    excess_nav = strategy_nav / benchmark_nav
    drawdown = strategy_nav / strategy_nav.cummax() - 1
    nav = pd.DataFrame(
        {
            "trade_date": trade_dates,
            "strategy_nav": strategy_nav,
            "benchmark_nav": benchmark_nav,
            "excess_nav": excess_nav,
            "daily_return": strategy_returns,
            "benchmark_return": benchmark_returns,
            "excess_return": strategy_returns - benchmark_returns,
            "drawdown": drawdown,
        }
    )
    total_value = INITIAL_CASH * strategy_nav
    position_ratio = np.clip(0.78 + rng.normal(0, 0.04, len(dates)), 0.55, 0.92)
    market_value = total_value * position_ratio
    cash = total_value - market_value
    daily_account = pd.DataFrame(
        {
            "trade_date": trade_dates,
            "total_value": total_value,
            "cash": cash,
            "market_value": market_value,
            "position_ratio": position_ratio,
            "daily_pnl": total_value.diff().fillna(total_value.iloc[0] - INITIAL_CASH),
            "daily_return": strategy_returns,
        }
    )
    symbols = [
        ("000001.XSHE", "平安银行"),
        ("600000.XSHG", "浦发银行"),
        ("000858.XSHE", "五粮液"),
    ]
    position_rows = []
    trade_rows = []
    order_rows = []
    for idx, trade_date in enumerate(trade_dates[::5]):
        for sid, (order_book_id, symbol) in enumerate(symbols):
            close = 10 + sid * 25 + idx * 0.3
            quantity = 1000 + sid * 200 + idx * 20
            market = close * quantity
            position_rows.append(
                {
                    "trade_date": trade_date,
                    "order_book_id": order_book_id,
                    "symbol": symbol,
                    "quantity": quantity,
                    "close": close,
                    "market_value": market,
                    "weight": market / float(total_value.iloc[min(idx * 5, len(total_value) - 1)]),
                    "pnl": rng.normal(300, 120),
                }
            )
            side = "BUY" if (idx + sid) % 2 == 0 else "SELL"
            amount = close * 100
            trade_rows.append(
                {
                    "trade_date": trade_date,
                    "datetime": f"{trade_date} 14:55:00",
                    "order_book_id": order_book_id,
                    "symbol": symbol,
                    "side": side,
                    "quantity": 100,
                    "price": close,
                    "amount": amount,
                    "commission": amount * 0.0003,
                    "tax": amount * 0.001 if side == "SELL" else 0,
                    "slippage": amount * 0.0001,
                    "realized_pnl": rng.normal(80, 60),
                }
            )
            order_rows.append(
                {
                    "trade_date": trade_date,
                    "datetime": f"{trade_date} 14:54:58",
                    "order_book_id": order_book_id,
                    "side": side,
                    "order_type": "MARKET",
                    "quantity": 100,
                    "price": close,
                    "status": "FILLED",
                    "message": "demo order",
                }
            )
    monthly_returns = (
        nav.assign(month=pd.to_datetime(nav["trade_date"]).dt.strftime("%Y-%m"))
        .groupby("month", as_index=False)["daily_return"]
        .apply(lambda x: (1 + x).prod() - 1)
        .rename(columns={"daily_return": "monthly_return"})
    )
    rolling_metrics = pd.DataFrame(
        {
            "trade_date": trade_dates,
            "rolling_20_return": nav["strategy_nav"].pct_change(20),
            "rolling_20_volatility": nav["daily_return"].rolling(20).std(ddof=0) * np.sqrt(252),
        }
    ).fillna(0)
    return {
        "nav": nav,
        "daily_account": daily_account,
        "positions": pd.DataFrame(position_rows),
        "trades": pd.DataFrame(trade_rows),
        "orders": pd.DataFrame(order_rows),
        "monthly_returns": monthly_returns,
        "rolling_metrics": rolling_metrics,
    }


if __name__ == "__main__":
    main()
