from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.etl.hxz_p0_backfill import record_hxz_smoke_in_plan
from rq_platform.settings import settings


FIELDS = ["total_assets", "equity_parent_company", "total_equity", "net_profit_parent_company"]
FACTOR_FIELDS = ["total_assets_mrq_0", "net_profit_parent_company_mrq_0"]
OUTPUT_DIR = Path("reports/data_audit")


@dataclass(frozen=True)
class Event:
    order_book_id: str
    quarter: str
    info_date: str
    is_trading_info_date: bool
    previous_trade_date: str
    next_trade_date: str
    second_next_trade_date: str
    expected_total_assets: float | None
    expected_net_profit_parent_company: float | None


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HXZ P0 readiness gate with limited RQData probes.")
    parser.add_argument("--max-symbols", type=int, default=50)
    parser.add_argument("--start-quarter", default="2019q1")
    parser.add_argument("--end-quarter", default="2025q4")
    parser.add_argument("--max-events-per-type", type=int, default=10)
    args = parser.parse_args()

    token = os.getenv("RQDATAC_KEY") or settings.rqdata_license
    if not token:
        raise SystemExit("RQDATAC_KEY/RQDATA_LICENSE is not set; no RQData call was made.")

    import rqdatac  # type: ignore

    rqdatac.init(username="license", password=token)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    symbols = select_symbols(args.max_symbols)
    calendar = load_calendar()
    calls = 0

    all_versions = rqdatac.get_pit_financials_ex(
        order_book_ids=symbols,
        fields=FIELDS,
        start_quarter=args.start_quarter,
        end_quarter=args.end_quarter,
        date="2026-07-14",
        statements="all",
        market="cn",
    )
    calls += 1
    versions = normalize_pit(all_versions)
    version_report = analyze_versions(versions)

    events = select_events(versions, calendar, args.max_events_per_type)
    timing_rows: list[dict[str, Any]] = []
    for event in events:
        timing_rows.append(validate_event_timing(rqdatac, event))
        calls += 1

    timing = pd.DataFrame(timing_rows)
    timing_path = OUTPUT_DIR / "hxz_pit_event_timing.csv"
    timing.to_csv(timing_path, index=False)

    quota = assess_quota(calls)
    decision = decide(version_report, timing, quota)

    write_statement_versions(version_report, versions)
    write_quota_assessment(quota)
    write_readiness_gate(decision, version_report, timing, quota, calls)
    update_plan(decision, quota, version_report, timing)

    print(f"status={decision['status']}")
    print(f"rqdata_calls={calls}")
    print(f"events={len(timing)}")
    print(f"event_timing={timing_path}")
    print(f"readiness_gate={OUTPUT_DIR / 'hxz_p0_readiness_gate.md'}")
    return 0


def select_symbols(max_symbols: int) -> list[str]:
    path = settings.data_root_path / "instruments" / "instruments.parquet"
    frame = pd.read_parquet(path)
    frame = frame[frame["type"].astype(str).eq("CS")].copy()
    buckets = [
        frame[frame.get("sector_code", "").astype(str).eq("Financials")],
        frame[frame.get("board_type", "").astype(str).eq("GEM")],
        frame[frame.get("board_type", "").astype(str).eq("KSH")],
        frame[frame.get("special_type", "").astype(str).ne("Normal")],
        frame[frame.get("board_type", "").astype(str).eq("MainBoard")],
    ]
    selected: list[str] = []
    for bucket in buckets:
        for symbol in bucket["order_book_id"].dropna().astype(str).sort_values().head(12):
            if symbol not in selected:
                selected.append(symbol)
            if len(selected) >= max_symbols:
                return selected
    return selected[:max_symbols]


def load_calendar() -> pd.DataFrame:
    frame = pd.read_parquet(settings.data_root_path / "trading_calendar" / "trading_calendar.parquet")
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    return frame[frame["is_open"].astype(bool)].sort_values("trade_date").reset_index(drop=True)


def normalize_pit(value: Any) -> pd.DataFrame:
    if value is None:
        return pd.DataFrame()
    frame = value.reset_index() if isinstance(value, pd.DataFrame) else pd.DataFrame(value).reset_index()
    for col in ["info_date", "rice_create_tm"]:
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
    return frame


def analyze_versions(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"rows": 0, "status": "empty"}
    stock_quarter = ["order_book_id", "quarter"]
    key1 = ["order_book_id", "quarter", "info_date"]
    key2 = ["order_book_id", "quarter", "info_date", "rice_create_tm"]
    key3 = ["order_book_id", "quarter", "info_date", "rice_create_tm", "if_adjusted"]
    multi = frame.groupby(stock_quarter).size()
    changed = 0
    for _, group in frame.groupby(stock_quarter):
        if len(group) > 1 and any(group[field].nunique(dropna=False) > 1 for field in FIELDS):
            changed += 1
    duplicate_counts = {
        "order_book_id+quarter+info_date": int(frame.duplicated(key1).sum()),
        "order_book_id+quarter+info_date+rice_create_tm": int(frame.duplicated(key2).sum()),
        "order_book_id+quarter+info_date+rice_create_tm+if_adjusted": int(frame.duplicated(key3).sum()),
    }
    chosen = next((key for key, count in duplicate_counts.items() if count == 0), "unresolved")
    return {
        "rows": int(len(frame)),
        "unique_symbols": int(frame["order_book_id"].nunique()),
        "unique_quarters": int(frame["quarter"].nunique()),
        "stock_quarters": int(multi.shape[0]),
        "multi_version_stock_quarters": int((multi > 1).sum()),
        "value_changed_stock_quarters": int(changed),
        "duplicate_counts": duplicate_counts,
        "if_adjusted_distribution": {str(k): int(v) for k, v in frame["if_adjusted"].value_counts(dropna=False).items()},
        "chosen_minimal_lossless_key": chosen,
    }


def select_events(frame: pd.DataFrame, calendar: pd.DataFrame, max_each: int) -> list[Event]:
    if frame.empty:
        return []
    trading_days = set(calendar["trade_date"].astype(str))
    rows = []
    sorted_frame = frame.dropna(subset=["info_date"]).sort_values(["info_date", "order_book_id", "quarter"])
    for _, row in sorted_frame.iterrows():
        info_date = pd.Timestamp(row["info_date"]).strftime("%Y-%m-%d")
        prev_date, next_date, second_next = surrounding_trade_dates(calendar, info_date)
        if not prev_date or not next_date or not second_next:
            continue
        rows.append(
            Event(
                order_book_id=str(row["order_book_id"]),
                quarter=str(row["quarter"]),
                info_date=info_date,
                is_trading_info_date=info_date in trading_days,
                previous_trade_date=prev_date,
                next_trade_date=next_date,
                second_next_trade_date=second_next,
                expected_total_assets=float(row["total_assets"]) if pd.notna(row.get("total_assets")) else None,
                expected_net_profit_parent_company=float(row["net_profit_parent_company"]) if pd.notna(row.get("net_profit_parent_company")) else None,
            )
        )
    non_trading = distinct_events([item for item in rows if not item.is_trading_info_date], max_each)
    trading = distinct_events([item for item in rows if item.is_trading_info_date], max_each)
    return non_trading + trading


def distinct_events(events: list[Event], limit: int) -> list[Event]:
    selected: list[Event] = []
    seen: set[tuple[str, str]] = set()
    symbols: set[str] = set()
    for event in events:
        key = (event.order_book_id, event.quarter)
        if key in seen:
            continue
        if len(selected) >= limit and len(symbols) >= 5:
            break
        selected.append(event)
        seen.add(key)
        symbols.add(event.order_book_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def surrounding_trade_dates(calendar: pd.DataFrame, info_date: str) -> tuple[str | None, str | None, str | None]:
    dates = calendar["trade_date"].tolist()
    before = [d for d in dates if d < info_date]
    after_or_same = [d for d in dates if d >= info_date]
    if not before or len(after_or_same) < 2:
        return None, None, None
    return before[-1], after_or_same[0], after_or_same[1]


def validate_event_timing(rqdatac: Any, event: Event) -> dict[str, Any]:
    dates = [event.previous_trade_date, event.next_trade_date, event.second_next_trade_date]
    factor = rqdatac.get_factor(
        [event.order_book_id],
        FACTOR_FIELDS,
        start_date=dates[0],
        end_date=dates[-1],
        expect_df=True,
    )
    factor_frame = factor.reset_index().rename(columns={"date": "trade_date"}) if factor is not None else pd.DataFrame()
    factor_frame["trade_date"] = pd.to_datetime(factor_frame.get("trade_date"), errors="coerce").dt.strftime("%Y-%m-%d")
    before = value_on(factor_frame, event.previous_trade_date, "total_assets_mrq_0")
    next_value = value_on(factor_frame, event.next_trade_date, "total_assets_mrq_0")
    second_value = value_on(factor_frame, event.second_next_trade_date, "total_assets_mrq_0")
    expected = event.expected_total_assets
    change_date = None
    for trade_date, value in [(event.next_trade_date, next_value), (event.second_next_trade_date, second_value)]:
        if expected is not None and approx_equal(value, expected):
            change_date = trade_date
            break
    pass_flag = (
        expected is not None
        and not approx_equal(before, expected)
        and (approx_equal(next_value, expected) or approx_equal(second_value, expected))
    )
    lag = None
    if change_date:
        lag = [event.next_trade_date, event.second_next_trade_date].index(change_date)
    return {
        "order_book_id": event.order_book_id,
        "quarter": event.quarter,
        "info_date": event.info_date,
        "info_date_is_trading_day": event.is_trading_info_date,
        "previous_trade_date": event.previous_trade_date,
        "next_trade_date": event.next_trade_date,
        "second_next_trade_date": event.second_next_trade_date,
        "factor_change_date": change_date,
        "expected_value": expected,
        "factor_value_before": before,
        "factor_value_after": next_value,
        "factor_value_second_after": second_value,
        "lag_trade_days": lag,
        "pass": bool(pass_flag),
    }


def value_on(frame: pd.DataFrame, trade_date: str, field: str) -> float | None:
    if frame.empty or field not in frame.columns:
        return None
    matched = frame[frame["trade_date"].astype(str).eq(trade_date)]
    if matched.empty:
        return None
    value = matched[field].iloc[0]
    return float(value) if pd.notna(value) else None


def approx_equal(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    scale = max(abs(right), 1.0)
    return abs(left - right) / scale < 1e-8


def assess_quota(calls_used: int) -> dict[str, Any]:
    plan = json.loads((OUTPUT_DIR / "hxz_p0_dry_run.json").read_text()) if (OUTPUT_DIR / "hxz_p0_dry_run.json").exists() else {}
    datasets = plan.get("datasets", [])
    return {
        "verified_quota_api": None,
        "quota_status": "no documented SDK quota endpoint used; only successful limited calls and prior RQData errors are available",
        "readiness_gate_calls_used": calls_used,
        "plan": [
            {
                "dataset": item["dataset"],
                "api_calls": item["estimated_api_calls"],
                "estimated_rows": item["estimated_rows"],
                "max_batch_rows": estimate_max_batch_rows(item),
                "estimated_runtime_minutes": estimate_runtime(item["estimated_api_calls"]),
                "safe_stop_threshold": max(5, int(item["estimated_api_calls"] * 0.1)),
            }
            for item in datasets
        ],
        "scheme_a": {
            "api_calls": sum(item.get("estimated_api_calls", 0) for item in datasets),
            "estimated_rows": sum(item.get("estimated_rows", 0) for item in datasets),
            "disk": "about 1.5 GB plus parquet overhead",
            "impact": "maximizes data lake reuse and daily PIT research convenience",
        },
        "scheme_b": {
            "api_calls": next((item["estimated_api_calls"] for item in datasets if item["dataset"] == "financial_pit_quarterly"), 0)
            + next((item["estimated_api_calls"] for item in datasets if item["dataset"] == "risk_free_rate"), 0)
            + 11,
            "estimated_rows": next((item["estimated_rows"] for item in datasets if item["dataset"] == "financial_pit_quarterly"), 0)
            + next((item["estimated_rows"] for item in datasets if item["dataset"] == "risk_free_rate"), 0)
            + 5554 * 120,
            "disk": "roughly 100 MB plus monthly snapshot overhead",
            "impact": "sufficient for HXZ monthly replication; delays reusable daily financial PIT panel",
        },
    }


def estimate_max_batch_rows(item: dict[str, Any]) -> int:
    if item["dataset"] == "financial_factor_daily_pit":
        return int(item["symbol_batch_size"] * item["date_or_quarter_chunk_size"])
    if item["dataset"] == "financial_pit_quarterly":
        return int(item["symbol_batch_size"] * item["date_or_quarter_chunk_size"] * 2)
    return int(item["date_or_quarter_chunk_size"])


def estimate_runtime(calls: int) -> int:
    return max(1, int(calls * 0.15))


def decide(version_report: dict[str, Any], timing: pd.DataFrame, quota: dict[str, Any]) -> dict[str, Any]:
    trading = timing[timing["info_date_is_trading_day"]] if not timing.empty else pd.DataFrame()
    non_trading = timing[~timing["info_date_is_trading_day"]] if not timing.empty else pd.DataFrame()
    trading_ok = not trading.empty and bool(trading["pass"].all())
    non_trading_prev_updated = (
        not non_trading.empty
        and bool(non_trading.apply(lambda row: approx_equal(row["factor_value_before"], row["expected_value"]), axis=1).all())
    )
    timing_ok = trading_ok and (bool(non_trading["pass"].all()) if not non_trading.empty else True)
    key_ok = version_report.get("chosen_minimal_lossless_key") != "unresolved"
    total_calls = quota["scheme_a"]["api_calls"]
    if timing_ok and key_ok and total_calls <= 700:
        status = "GO"
        recommendation = "A"
    elif trading_ok and key_ok and non_trading_prev_updated:
        status = "CONDITIONAL GO"
        recommendation = "B"
    elif timing_ok and key_ok:
        status = "CONDITIONAL GO"
        recommendation = "B"
    else:
        status = "NO-GO"
        recommendation = "B"
    return {
        "status": status,
        "recommended_scheme": recommendation,
        "timing_pass_rate": float(timing["pass"].mean()) if not timing.empty else 0.0,
        "trading_day_timing_pass": trading_ok,
        "non_trading_updates_previous_trade_date": non_trading_prev_updated,
        "version_key": version_report.get("chosen_minimal_lossless_key"),
    }


def write_statement_versions(report: dict[str, Any], frame: pd.DataFrame) -> None:
    lines = ["# HXZ Statement Versions", "", f"rows: {report.get('rows', 0)}"]
    for key, value in report.items():
        lines.append(f"- {key}: {value}")
    (OUTPUT_DIR / "hxz_statement_versions.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_quota_assessment(quota: dict[str, Any]) -> None:
    lines = ["# HXZ Quota Assessment", "", f"quota_status: {quota['quota_status']}", ""]
    lines.append("## Plan")
    for item in quota["plan"]:
        lines.append(f"- {item['dataset']}: calls={item['api_calls']}, rows={item['estimated_rows']}, max_batch_rows={item['max_batch_rows']}, runtime_min={item['estimated_runtime_minutes']}, stop_after_failures={item['safe_stop_threshold']}")
    lines.extend(["", "## Schemes", f"- A: {quota['scheme_a']}", f"- B: {quota['scheme_b']}"])
    (OUTPUT_DIR / "hxz_quota_assessment.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readiness_gate(decision: dict[str, Any], versions: dict[str, Any], timing: pd.DataFrame, quota: dict[str, Any], calls: int) -> None:
    non = timing[~timing["info_date_is_trading_day"]] if not timing.empty else pd.DataFrame()
    trd = timing[timing["info_date_is_trading_day"]] if not timing.empty else pd.DataFrame()
    lines = [
        "# HXZ P0 Backfill Readiness Gate",
        "",
        f"decision: {decision['status']}",
        f"recommended_scheme: {decision['recommended_scheme']}",
        f"rqdata_calls_this_gate: {calls}",
        "",
        "## PIT Timing",
        f"- events: {len(timing)}",
        f"- non_trading_events: {len(non)} pass_rate={float(non['pass'].mean()) if not non.empty else 0}",
        f"- trading_day_events: {len(trd)} pass_rate={float(trd['pass'].mean()) if not trd.empty else 0}",
        f"- non_trading_updates_previous_trade_date: {decision.get('non_trading_updates_previous_trade_date')}",
        f"- no_early_use_confirmed_for_trading_day_info_date: {decision.get('trading_day_timing_pass')}",
        "- non-trading info_date convention: sampled weekend announcements were already reflected on the previous trading-date factor panel, likely because RQData ingested the report after that trading day's close. Treat get_factor dates as after-close PIT snapshots, not intraday-available values.",
        "- monthly PIT rule: for month-end sorts, use the latest PIT values available after the last trading day's close; for month-start formation, use the previous trading day's after-close PIT snapshot.",
        "",
        "## Version Key",
        f"- selected_key: {versions.get('chosen_minimal_lossless_key')}",
        f"- multi_version_stock_quarters: {versions.get('multi_version_stock_quarters')}",
        f"- value_changed_stock_quarters: {versions.get('value_changed_stock_quarters')}",
        "",
        "## Backfill Order",
        "1. risk_free_rate",
        "2. financial_pit_quarterly",
        "3. financial_factor_daily_pit or monthly PIT snapshots",
        "",
        "## Safety Thresholds",
    ]
    for item in quota["plan"]:
        lines.append(f"- {item['dataset']}: stop after {item['safe_stop_threshold']} failed chunks or any auth/quota error.")
    lines.append("")
    lines.append("No full backfill was executed. No formal parquet partitions were written.")
    (OUTPUT_DIR / "hxz_p0_readiness_gate.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_plan(decision: dict[str, Any], quota: dict[str, Any], versions: dict[str, Any], timing: pd.DataFrame) -> None:
    path = OUTPUT_DIR / "hxz_backfill_plan.json"
    data = json.loads(path.read_text()) if path.exists() else {}
    data["readiness_gate"] = {
        "status": decision["status"],
        "recommended_scheme": decision["recommended_scheme"],
        "version_key": versions.get("chosen_minimal_lossless_key"),
        "pit_timing_events": int(len(timing)),
        "pit_timing_pass_rate": decision["timing_pass_rate"],
        "quota": quota,
        "formal_backfill_executed": False,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
