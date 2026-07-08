from __future__ import annotations

import math
from typing import Any

import pandas as pd

from rq_platform.backtest.current_store import CurrentBacktestNotFound, CurrentBacktestStore


TABLE_LIMITS = {
    "account": 100,
    "trades": 200,
    "orders": 200,
    "logs": 500,
}


SUMMARY_METRICS = [
    ("strategy_name", "策略名称", "text"),
    ("run_id", "Run ID", "text"),
    ("start_date", "开始日期", "text"),
    ("end_date", "结束日期", "text"),
    ("initial_cash", "初始资金", "money"),
    ("final_value", "最终资产", "money"),
    ("total_return", "累计收益", "percent"),
    ("annual_return", "年化收益", "percent"),
    ("annual_volatility", "年化波动", "percent"),
    ("sharpe", "夏普比率", "ratio"),
    ("max_drawdown", "最大回撤", "percent"),
    ("benchmark_return", "基准收益", "percent"),
    ("benchmark_annual_return", "基准年化", "percent"),
    ("excess_return", "超额收益", "percent"),
    ("tracking_error", "跟踪误差", "percent"),
    ("information_ratio", "信息比率", "ratio"),
    ("win_rate", "胜率", "percent"),
    ("trade_count", "交易次数", "integer"),
]

BENCHMARK_RELATED_METRICS = {
    "benchmark_return",
    "benchmark_annual_return",
    "excess_return",
    "tracking_error",
    "information_ratio",
}


def load_current_dashboard_data() -> dict[str, Any]:
    store = CurrentBacktestStore()
    if not store.current_exists():
        return _empty_dashboard()

    summary = _with_benchmark_defaults(_read_json(store, "summary.json"))
    nav = _read_csv_records(store, "nav.csv")
    account = _read_csv_records(store, "daily_account.csv", tail=TABLE_LIMITS["account"])
    positions_df = _read_csv(store, "positions.csv")
    positions, latest_position_date = _latest_positions(positions_df)
    trades = _read_csv_records(store, "trades.csv", tail=TABLE_LIMITS["trades"])
    orders = _read_csv_records(store, "orders.csv", tail=TABLE_LIMITS["orders"])
    logs = _read_logs(store)

    return {
        "exists": True,
        "summary": summary,
        "summary_metrics": _summary_metrics(summary),
        "nav": nav,
        "account": account,
        "positions": positions,
        "latest_position_date": latest_position_date,
        "trades": trades,
        "orders": orders,
        "logs": logs,
        "download_url": "/backtests/current/download",
    }


def format_value(value: Any, kind: str = "text") -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    if kind == "percent":
        return f"{float(value) * 100:.2f}%"
    if kind == "money":
        return f"{float(value):,.2f}"
    if kind == "ratio":
        return f"{float(value):.3f}"
    if kind == "integer":
        return f"{int(value):,}"
    return str(value)


def table_columns(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return []
    return list(records[0].keys())


def _empty_dashboard() -> dict[str, Any]:
    return {
        "exists": False,
        "summary": {},
        "summary_metrics": [],
        "nav": [],
        "account": [],
        "positions": [],
        "latest_position_date": None,
        "trades": [],
        "orders": [],
        "logs": "",
        "download_url": None,
    }


def _with_benchmark_defaults(summary: dict[str, Any]) -> dict[str, Any]:
    clean = dict(summary)
    fallback_used = bool(clean.get("benchmark_fallback_used", False))
    clean.setdefault("benchmark_missing", bool(clean.get("benchmark_missing", False)))
    clean.setdefault("benchmark_fallback_used", fallback_used)
    clean.setdefault("benchmark_warning", None)
    clean.setdefault("benchmark_metrics_reliable", not bool(clean["benchmark_fallback_used"]))
    clean.setdefault("benchmark", clean.get("benchmark"))
    return clean


def _read_json(store: CurrentBacktestStore, filename: str) -> dict:
    try:
        return store.read_current_json(filename)
    except (CurrentBacktestNotFound, ValueError):
        return {}


def _read_csv(store: CurrentBacktestStore, filename: str) -> pd.DataFrame:
    try:
        return store.read_current_csv(filename)
    except (CurrentBacktestNotFound, ValueError):
        return pd.DataFrame()


def _read_csv_records(
    store: CurrentBacktestStore, filename: str, tail: int | None = None
) -> list[dict[str, Any]]:
    frame = _read_csv(store, filename)
    if frame.empty:
        return []
    if tail is not None:
        frame = frame.tail(tail)
    clean = frame.where(pd.notna(frame), None)
    return clean.to_dict(orient="records")


def _latest_positions(frame: pd.DataFrame) -> tuple[list[dict[str, Any]], str | None]:
    if frame.empty or "trade_date" not in frame.columns:
        return [], None
    latest_date = str(frame["trade_date"].max())
    latest = frame[frame["trade_date"] == latest_date]
    latest = latest.where(pd.notna(latest), None)
    return latest.to_dict(orient="records"), latest_date


def _read_logs(store: CurrentBacktestStore) -> str:
    try:
        logs = store.read_current_text("logs.txt")
    except (CurrentBacktestNotFound, ValueError):
        return ""
    lines = logs.splitlines()
    return "\n".join(lines[-TABLE_LIMITS["logs"]:])


def _summary_metrics(summary: dict[str, Any]) -> list[dict[str, Any]]:
    benchmark_reliable = bool(summary.get("benchmark_metrics_reliable", True))
    items = []
    for key, label, kind in SUMMARY_METRICS:
        unreliable = (not benchmark_reliable) and key in BENCHMARK_RELATED_METRICS
        items.append(
            {
            "key": key,
            "label": label,
                "value": "N/A / unreliable" if unreliable else format_value(summary.get(key), kind),
                "unreliable": unreliable,
            }
        )
    return items
