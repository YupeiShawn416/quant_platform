from __future__ import annotations

from dataclasses import dataclass


MANIFEST_JSON = "manifest.json"
CONFIG_JSON = "config.json"
SUMMARY_JSON = "summary.json"
SUMMARY_CSV = "summary.csv"
NAV_CSV = "nav.csv"
DAILY_ACCOUNT_CSV = "daily_account.csv"
POSITIONS_CSV = "positions.csv"
TRADES_CSV = "trades.csv"
ORDERS_CSV = "orders.csv"
LOGS_TXT = "logs.txt"
MONTHLY_RETURNS_CSV = "monthly_returns.csv"
ROLLING_METRICS_CSV = "rolling_metrics.csv"
CHARTS_JSON = "charts.json"
ERROR_JSON = "error.json"

STANDARD_RESULT_FILES = [
    MANIFEST_JSON,
    CONFIG_JSON,
    SUMMARY_JSON,
    SUMMARY_CSV,
    NAV_CSV,
    DAILY_ACCOUNT_CSV,
    POSITIONS_CSV,
    TRADES_CSV,
    ORDERS_CSV,
    LOGS_TXT,
    MONTHLY_RETURNS_CSV,
    ROLLING_METRICS_CSV,
    CHARTS_JSON,
    ERROR_JSON,
]

NAV_COLUMNS = [
    "trade_date",
    "strategy_nav",
    "benchmark_nav",
    "excess_nav",
    "daily_return",
    "benchmark_return",
    "excess_return",
    "drawdown",
]

DAILY_ACCOUNT_COLUMNS = [
    "trade_date",
    "total_value",
    "cash",
    "market_value",
    "position_ratio",
    "daily_pnl",
    "daily_return",
]

POSITIONS_COLUMNS = [
    "trade_date",
    "order_book_id",
    "symbol",
    "quantity",
    "close",
    "market_value",
    "weight",
    "pnl",
]

TRADES_COLUMNS = [
    "trade_date",
    "datetime",
    "order_book_id",
    "symbol",
    "side",
    "quantity",
    "price",
    "amount",
    "commission",
    "tax",
    "slippage",
    "realized_pnl",
]

ORDERS_COLUMNS = [
    "trade_date",
    "datetime",
    "order_book_id",
    "side",
    "order_type",
    "quantity",
    "price",
    "status",
    "message",
]

SUMMARY_FIELDS = [
    "run_id",
    "strategy_name",
    "start_date",
    "end_date",
    "initial_cash",
    "final_value",
    "total_return",
    "annual_return",
    "annual_volatility",
    "sharpe",
    "max_drawdown",
    "benchmark_return",
    "excess_return",
    "information_ratio",
    "win_rate",
    "trade_count",
    "created_at",
]


@dataclass(frozen=True)
class ResultFileSpec:
    filename: str
    required_columns: list[str]


CSV_FILE_SPECS = {
    NAV_CSV: ResultFileSpec(NAV_CSV, NAV_COLUMNS),
    DAILY_ACCOUNT_CSV: ResultFileSpec(DAILY_ACCOUNT_CSV, DAILY_ACCOUNT_COLUMNS),
    POSITIONS_CSV: ResultFileSpec(POSITIONS_CSV, POSITIONS_COLUMNS),
    TRADES_CSV: ResultFileSpec(TRADES_CSV, TRADES_COLUMNS),
    ORDERS_CSV: ResultFileSpec(ORDERS_CSV, ORDERS_COLUMNS),
    SUMMARY_CSV: ResultFileSpec(SUMMARY_CSV, SUMMARY_FIELDS),
}
