from __future__ import annotations

import math
from typing import Any

import pandas as pd

from rq_platform.backtest.current_store import CurrentBacktestNotFound, CurrentBacktestStore
from rq_platform.backtest.run_registry import BacktestRunRegistry
from rq_platform.backtest.run_store import BacktestRunResultNotFound, BacktestRunStore
from rq_platform.auth import load_researcher_tokens


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

    return _load_dashboard_data(
        reader=_CurrentReader(store),
        download_url="/backtests/current/download",
        url_prefix="/ui/backtests/current",
    )


def load_run_dashboard_data(run_id: str) -> dict[str, Any]:
    registry = BacktestRunRegistry()
    record = registry.get(run_id)
    if record is None:
        data = _empty_dashboard()
        data["missing_message"] = "Run ID 不存在。"
        return data
    if not record.get("result_available"):
        data = _empty_dashboard()
        data["record"] = record
        data["missing_message"] = "This run record exists, but result files are no longer available."
        return data
    return _load_dashboard_data(
        reader=_RunReader(BacktestRunStore(), record["run_id"]),
        download_url=f"/backtests/runs/{record['run_id']}/download",
        url_prefix=f"/ui/backtests/runs/{record['run_id']}",
        record=record,
    )


def load_runs_dashboard_data(
    limit: int = 100,
    researcher_id: str | None = None,
    researcher_name: str | None = None,
) -> dict[str, Any]:
    runs = BacktestRunRegistry().list_runs(
        limit=limit,
        researcher_id=researcher_id,
        researcher_name=researcher_name,
    )
    return {
        "exists": True,
        "runs": runs,
        "download_url": None,
        "filters": {
            "researcher_id": researcher_id or "",
            "researcher_name": researcher_name or "",
        },
    }


def load_researcher_usage_dashboard_data() -> dict[str, Any]:
    usage = BacktestRunRegistry().researcher_usage()
    rows: list[dict[str, Any]] = []
    for token in load_researcher_tokens():
        row = usage.pop(
            token.researcher_id,
            {
                "researcher_id": token.researcher_id,
                "name": token.name,
                "total_runs": 0,
                "success_runs": 0,
                "failed_runs": 0,
                "last_used_at": None,
            },
        )
        row["name"] = token.name
        row["enabled"] = token.enabled
        rows.append(row)
    for row in usage.values():
        row["enabled"] = True
        rows.append(row)
    rows = sorted(rows, key=lambda item: (str(item.get("researcher_id") or "")))
    return {"exists": True, "researchers": rows, "download_url": None}


def _load_dashboard_data(
    *,
    reader: "_ResultReader",
    download_url: str,
    url_prefix: str,
    record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = _with_benchmark_defaults(_read_json(reader, "summary.json"))
    nav = _read_csv_records(reader, "nav.csv")
    account = _read_csv_records(reader, "daily_account.csv", tail=TABLE_LIMITS["account"])
    positions_df = _read_csv(reader, "positions.csv")
    positions, latest_position_date = _latest_positions(positions_df)
    trades = _read_csv_records(reader, "trades.csv", tail=TABLE_LIMITS["trades"])
    orders = _read_csv_records(reader, "orders.csv", tail=TABLE_LIMITS["orders"])
    logs = _read_logs(reader)

    return {
        "exists": True,
        "record": record or {},
        "summary": summary,
        "summary_metrics": _summary_metrics(summary),
        "nav": nav,
        "account": account,
        "positions": positions,
        "latest_position_date": latest_position_date,
        "trades": trades,
        "orders": orders,
        "logs": logs,
        "download_url": download_url,
        "url_prefix": url_prefix,
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
        "url_prefix": "/ui/backtests/current",
        "record": {},
        "missing_message": None,
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


class _ResultReader:
    def read_json(self, filename: str) -> dict:
        raise NotImplementedError

    def read_csv(self, filename: str) -> pd.DataFrame:
        raise NotImplementedError

    def read_text(self, filename: str) -> str:
        raise NotImplementedError


class _CurrentReader(_ResultReader):
    def __init__(self, store: CurrentBacktestStore):
        self.store = store

    def read_json(self, filename: str) -> dict:
        return self.store.read_current_json(filename)

    def read_csv(self, filename: str) -> pd.DataFrame:
        return self.store.read_current_csv(filename)

    def read_text(self, filename: str) -> str:
        return self.store.read_current_text(filename)


class _RunReader(_ResultReader):
    def __init__(self, store: BacktestRunStore, run_id: str):
        self.store = store
        self.run_id = run_id

    def read_json(self, filename: str) -> dict:
        return self.store.read_json(self.run_id, filename)

    def read_csv(self, filename: str) -> pd.DataFrame:
        return self.store.read_csv(self.run_id, filename)

    def read_text(self, filename: str) -> str:
        return self.store.read_text(self.run_id, filename)


def _read_json(store: _ResultReader, filename: str) -> dict:
    try:
        return store.read_json(filename)
    except (CurrentBacktestNotFound, BacktestRunResultNotFound, ValueError):
        return {}


def _read_csv(store: _ResultReader, filename: str) -> pd.DataFrame:
    try:
        return store.read_csv(filename)
    except (CurrentBacktestNotFound, BacktestRunResultNotFound, ValueError):
        return pd.DataFrame()


def _read_csv_records(
    store: _ResultReader, filename: str, tail: int | None = None
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


def _read_logs(store: _ResultReader) -> str:
    try:
        logs = store.read_text("logs.txt")
    except (CurrentBacktestNotFound, BacktestRunResultNotFound, ValueError):
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
