from __future__ import annotations

import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from rq_platform.data.data_loader import ResearchDataLoader


DEFAULT_PILOT_ROOT = Path("/Users/yupeishen/Desktop/vix_beta_q5_long_only_pilot")
DEFAULT_SAME_DAY_PACKAGE = Path("/tmp/vix_beta_q5_long_only_package.zip")
DEFAULT_LAGGED_PACKAGE = Path("/tmp/vix_beta_q5_long_only_lagged_package.zip")


def load_pilot_config(pilot_root: str | Path = DEFAULT_PILOT_ROOT) -> dict[str, Any]:
    path = Path(pilot_root) / "configs" / "strategy.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_pilot_weights(pilot_root: str | Path = DEFAULT_PILOT_ROOT) -> pd.DataFrame:
    root = Path(pilot_root)
    parquet_path = root / "data" / "output" / "weights.parquet"
    csv_path = root / "data" / "output" / "weights.csv"
    frame = pd.read_parquet(parquet_path) if parquet_path.exists() else pd.read_csv(csv_path)
    return normalize_weights(frame)


def normalize_weights(weights: pd.DataFrame) -> pd.DataFrame:
    frame = weights.copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame["order_book_id"] = frame["order_book_id"].astype(str)
    frame["target_weight"] = pd.to_numeric(frame["target_weight"], errors="coerce")
    frame = frame.dropna(subset=["target_weight"])
    frame = frame[frame["target_weight"] > 0]
    return frame.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)


def build_lagged_weights(weights: pd.DataFrame, trading_dates: list[str]) -> pd.DataFrame:
    frame = normalize_weights(weights)
    dates = [pd.Timestamp(date).strftime("%Y-%m-%d") for date in trading_dates]
    next_date = {date: dates[index + 1] for index, date in enumerate(dates[:-1])}
    output = frame[frame["trade_date"].isin(next_date)].copy()
    output["source_trade_date"] = output["trade_date"]
    output["trade_date"] = output["trade_date"].map(next_date)
    return output.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)


def build_weights_package(
    config: dict[str, Any],
    weights: pd.DataFrame,
    output_path: str | Path,
    run_id: str | None = None,
    strategy_name: str | None = None,
) -> Path:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    run_config = dict(config["run"])
    run_config["mode"] = "weights"
    run_config["strategy_name"] = strategy_name or str(config["strategy_name"])
    if run_id:
        run_config["run_id"] = run_id
    manifest = {
        "package_version": str(config.get("package_version", "1.0")),
        "strategy_id": str(config["strategy_id"]),
        "strategy_name": run_config["strategy_name"],
        "author": str(config.get("author", "researcher")),
        "mode": "weights",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "description": str(config.get("description", "")),
    }
    weights = normalize_weights(weights)[["trade_date", "order_book_id", "target_weight"]]
    with tempfile.TemporaryDirectory(prefix="vix_q5_package_") as tmp:
        package_dir = Path(tmp)
        weights_path = package_dir / "weights.parquet"
        weights.to_parquet(weights_path, index=False)
        run_config["weight_file"] = "weights.parquet"
        (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (package_dir / "config.json").write_text(json.dumps(run_config, indent=2), encoding="utf-8")
        (package_dir / "README.md").write_text(
            f"# {run_config['strategy_name']}\n\nGenerated for VIX Q5 audit.\n",
            encoding="utf-8",
        )
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package_dir.iterdir()):
                archive.write(path, arcname=path.name)
    return output


def load_trading_dates(start_date: str, end_date: str) -> list[str]:
    loader = ResearchDataLoader()
    sample = loader.load_index_prices(
        index_ids=["000300.XSHG"],
        start_date=start_date,
        end_date=end_date,
    )
    if sample.empty:
        raise ValueError("local index calendar sample is empty; run make update-index-2025 first")
    return sorted(sample["trade_date"].astype(str).unique().tolist())


def compute_exposure_summary(weights: pd.DataFrame, loader: ResearchDataLoader | None = None) -> dict[str, Any]:
    loader = loader or ResearchDataLoader()
    frame = normalize_weights(weights)
    start = str(frame["trade_date"].min())
    end = str(frame["trade_date"].max())
    symbols = sorted(frame["order_book_id"].unique().tolist())
    valuation = loader.load_valuation(symbols=symbols, start_date=start, end_date=end)
    industry = loader.load_industry(symbols=symbols, start_date=start, end_date=end)
    components = loader.load_index_components(
        index_ids=["000300.XSHG", "000905.XSHG", "000852.XSHG"],
        start_date=start,
        end_date=end,
    )

    merged_val = frame.merge(valuation, on=["trade_date", "order_book_id"], how="left")
    valuation_summary = {
        column: _weighted_daily_average(merged_val, column)
        for column in [
            "market_cap",
            "float_market_cap",
            "pe_ratio",
            "pb_ratio",
            "ps_ratio",
            "pcf_ratio",
            "turnover_rate",
        ]
    }
    industry_exposure = _industry_exposure(frame, industry)
    index_overlap = _index_overlap(frame, components)
    return {
        "date_range": [start, end],
        "dates": int(frame["trade_date"].nunique()),
        "unique_symbols": int(frame["order_book_id"].nunique()),
        "average_holdings": float(frame.groupby("trade_date")["order_book_id"].nunique().mean()),
        "valuation_weighted_average": valuation_summary,
        "top_industries_by_average_weight": industry_exposure.head(15).to_dict("records"),
        "index_overlap_average_weight": index_overlap,
        "missing_valuation_rows": int(merged_val["market_cap"].isna().sum()) if "market_cap" in merged_val else len(merged_val),
        "missing_industry_rows": _missing_industry_rows(frame, industry),
    }


def compare_summaries(same_day: dict[str, Any], lagged: dict[str, Any]) -> pd.DataFrame:
    metrics = [
        "total_return",
        "annual_return",
        "sharpe",
        "max_drawdown",
        "benchmark_return",
        "excess_return",
        "tracking_error",
        "information_ratio",
        "trade_count",
    ]
    rows = []
    for metric in metrics:
        same = same_day.get(metric)
        lag = lagged.get(metric)
        rows.append(
            {
                "metric": metric,
                "same_day": same,
                "lagged": lag,
                "difference": _numeric_or_none(lag) - _numeric_or_none(same)
                if _numeric_or_none(lag) is not None and _numeric_or_none(same) is not None
                else None,
            }
        )
    return pd.DataFrame(rows)


def render_exposure_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# VIX Q5 Exposure Audit",
        "",
        "## Scope",
        "",
        f"- Date range: `{summary['date_range'][0]}` to `{summary['date_range'][1]}`",
        f"- Dates: `{summary['dates']}`",
        f"- Unique symbols: `{summary['unique_symbols']}`",
        f"- Average holdings: `{summary['average_holdings']:.2f}`",
        f"- Missing valuation rows: `{summary['missing_valuation_rows']}`",
        f"- Missing industry rows: `{summary['missing_industry_rows']}`",
        "",
        "## Weighted Averages",
        "",
        "| Metric | Average |",
        "|---|---:|",
    ]
    for key, value in summary["valuation_weighted_average"].items():
        lines.append(f"| {key} | {_fmt(value)} |")
    lines += ["", "## Top Industries", "", "| Industry | Average Weight |", "|---|---:|"]
    for row in summary["top_industries_by_average_weight"]:
        lines.append(f"| {row['industry_name']} | {_fmt(row['average_weight'])} |")
    lines += ["", "## Index Overlap", "", "| Index | Average Weight In Index |", "|---|---:|"]
    for key, value in summary["index_overlap_average_weight"].items():
        lines.append(f"| {key} | {_fmt(value)} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "This audit is descriptive. It uses local `valuation_1d`, `industry_classification`, "
        "and `index_components` data to characterize the existing VIX Q5 Long Only weights. "
        "It does not by itself prove causality or remove timing risk.",
        "",
    ]
    return "\n".join(lines)


def render_comparison_markdown(comparison: pd.DataFrame, same_day: dict[str, Any], lagged: dict[str, Any]) -> str:
    lines = [
        "# VIX Q5 Same-Day vs Lagged Comparison",
        "",
        "## Runs",
        "",
        f"- Same-day run_id: `{same_day.get('run_id')}`",
        f"- Lagged run_id: `{lagged.get('run_id')}`",
        f"- Same-day benchmark reliable: `{same_day.get('benchmark_metrics_reliable')}`",
        f"- Lagged benchmark reliable: `{lagged.get('benchmark_metrics_reliable')}`",
        "",
        "## Metrics",
        "",
        "| Metric | Same-Day | Lagged | Difference (Lagged - Same-Day) |",
        "|---|---:|---:|---:|",
    ]
    for row in comparison.to_dict("records"):
        lines.append(
            f"| {row['metric']} | {_fmt(row['same_day'])} | {_fmt(row['lagged'])} | {_fmt(row['difference'])} |"
        )
    lines += [
        "",
        "## Interpretation",
        "",
        "The lagged package shifts each target-weight date to the next local trading date. "
        "This is a stricter timing assumption than same-day close-to-close execution and is intended "
        "to reveal whether same-day signal usage materially inflates apparent performance.",
        "",
    ]
    return "\n".join(lines)


def _weighted_daily_average(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns:
        return None
    clean = frame.dropna(subset=[column, "target_weight"]).copy()
    if clean.empty:
        return None
    clean["_weighted"] = clean[column].astype(float) * clean["target_weight"].astype(float)
    daily = clean.groupby("trade_date")["_weighted"].sum()
    return float(daily.mean()) if not daily.empty else None


def _industry_exposure(weights: pd.DataFrame, industry: pd.DataFrame) -> pd.DataFrame:
    if industry.empty:
        return pd.DataFrame(columns=["industry_name", "average_weight"])
    merged = weights.merge(
        industry[["trade_date", "order_book_id", "industry_name"]],
        on=["trade_date", "order_book_id"],
        how="left",
    )
    merged["industry_name"] = merged["industry_name"].fillna("UNKNOWN")
    daily = merged.groupby(["trade_date", "industry_name"], as_index=False)["target_weight"].sum()
    result = (
        daily.groupby("industry_name", as_index=False)["target_weight"]
        .mean()
        .rename(columns={"target_weight": "average_weight"})
        .sort_values("average_weight", ascending=False)
        .reset_index(drop=True)
    )
    return result


def _index_overlap(weights: pd.DataFrame, components: pd.DataFrame) -> dict[str, float]:
    result = {}
    if components.empty:
        return result
    for index_id, index_frame in components.groupby("index_id"):
        keys = index_frame[["trade_date", "order_book_id"]].drop_duplicates()
        merged = weights.merge(keys.assign(in_index=True), on=["trade_date", "order_book_id"], how="left")
        daily = merged[merged["in_index"].eq(True)].groupby("trade_date")["target_weight"].sum()
        result[str(index_id)] = float(daily.mean()) if not daily.empty else 0.0
    return result


def _missing_industry_rows(weights: pd.DataFrame, industry: pd.DataFrame) -> int:
    if industry.empty:
        return len(weights)
    merged = weights.merge(
        industry[["trade_date", "order_book_id", "industry_name"]],
        on=["trade_date", "order_book_id"],
        how="left",
    )
    return int(merged["industry_name"].isna().sum())


def _numeric_or_none(value) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _fmt(value) -> str:
    number = _numeric_or_none(value)
    if number is None:
        return "N/A"
    return f"{number:.6f}"
