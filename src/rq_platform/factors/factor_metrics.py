from __future__ import annotations

import numpy as np
import pandas as pd


def coverage_by_date(values: pd.DataFrame, universe_counts: pd.Series | None = None) -> pd.DataFrame:
    grouped = values.groupby("trade_date")
    rows = grouped.agg(
        total_count=("order_book_id", "size"),
        valid_count=("factor_score", lambda s: int(s.notna().sum())),
        missing_count=("factor_score", lambda s: int(s.isna().sum())),
    ).reset_index()
    rows["missing_rate"] = rows["missing_count"] / rows["total_count"].replace(0, np.nan)
    if universe_counts is None:
        rows["coverage_rate"] = rows["valid_count"] / rows["total_count"].replace(0, np.nan)
    else:
        rows["universe_count"] = rows["trade_date"].map(universe_counts)
        rows["coverage_rate"] = rows["valid_count"] / rows["universe_count"].replace(0, np.nan)
    return rows.fillna(0)


def extreme_stats(values: pd.DataFrame) -> dict[str, float | None]:
    s = pd.to_numeric(values["factor_value"], errors="coerce").dropna()
    if s.empty:
        return {key: None for key in ["p1", "p5", "p50", "p95", "p99"]}
    return {
        "p1": float(s.quantile(0.01)),
        "p5": float(s.quantile(0.05)),
        "p50": float(s.quantile(0.50)),
        "p95": float(s.quantile(0.95)),
        "p99": float(s.quantile(0.99)),
    }


def forward_returns(prices: pd.DataFrame, horizons: tuple[int, ...] = (1, 5, 20)) -> pd.DataFrame:
    frame = prices[["trade_date", "order_book_id", "close"]].copy()
    frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
    frame = frame.sort_values(["order_book_id", "trade_date"])
    close = pd.to_numeric(frame["close"], errors="coerce")
    grouped = close.groupby(frame["order_book_id"])
    for horizon in horizons:
        frame[f"fwd_ret_{horizon}d"] = grouped.transform(lambda s: s.shift(-horizon) / s - 1.0)
    return frame.drop(columns=["close"])


def ic_daily(factor_with_returns: pd.DataFrame, horizons: tuple[int, ...] = (1, 5, 20)) -> pd.DataFrame:
    rows = []
    for trade_date, part in factor_with_returns.groupby("trade_date"):
        row = {"trade_date": trade_date}
        for horizon in horizons:
            col = f"fwd_ret_{horizon}d"
            valid = part[["factor_score", col]].dropna()
            row[f"ic_{horizon}d"] = float(valid["factor_score"].corr(valid[col], method="spearman")) if len(valid) >= 2 else np.nan
        rows.append(row)
    return pd.DataFrame(rows).sort_values("trade_date")


def ic_summary(ic: pd.DataFrame, column: str = "ic_5d") -> dict[str, float | None]:
    s = pd.to_numeric(ic.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    if s.empty:
        return {"ic_mean": None, "ic_std": None, "icir": None, "ic_positive_ratio": None, "ic_abs_gt_002_ratio": None}
    std = float(s.std(ddof=0))
    return {
        "ic_mean": float(s.mean()),
        "ic_std": std,
        "icir": float(s.mean() / std) if std else None,
        "ic_positive_ratio": float((s > 0).mean()),
        "ic_abs_gt_002_ratio": float((s.abs() > 0.02).mean()),
    }


def group_returns(factor_with_returns: pd.DataFrame, groups: int = 5, return_col: str = "fwd_ret_5d") -> pd.DataFrame:
    rows = []
    for trade_date, part in factor_with_returns.dropna(subset=["factor_score", return_col]).groupby("trade_date"):
        if len(part) < groups:
            continue
        ranked = part.copy()
        ranked["group"] = pd.qcut(ranked["factor_score"].rank(method="first"), groups, labels=False) + 1
        for group, group_part in ranked.groupby("group"):
            returns = pd.to_numeric(group_part[return_col], errors="coerce").dropna()
            rows.append(
                {
                    "trade_date": trade_date,
                    "group": int(group),
                    "mean_forward_return": float(returns.mean()) if not returns.empty else np.nan,
                    "win_rate": float((returns > 0).mean()) if not returns.empty else np.nan,
                    "sample_count": int(len(returns)),
                }
            )
    return pd.DataFrame(rows)


def group_nav(group_return_frame: pd.DataFrame) -> pd.DataFrame:
    if group_return_frame.empty:
        return pd.DataFrame(columns=["trade_date", "group", "nav"])
    rows = group_return_frame[["trade_date", "group", "mean_forward_return"]].copy()
    rows = rows.sort_values(["group", "trade_date"])
    rows["nav"] = (1.0 + rows["mean_forward_return"].fillna(0)).groupby(rows["group"]).cumprod()
    pivot = rows.pivot_table(index="trade_date", columns="group", values="mean_forward_return")
    if 1 in pivot.columns and max(pivot.columns) in pivot.columns:
        long_short = pivot[max(pivot.columns)].fillna(0) - pivot[1].fillna(0)
        ls_nav = (1.0 + long_short).cumprod().reset_index()
        ls_nav["group"] = "long_short"
        ls_nav = ls_nav.rename(columns={0: "nav"})
        rows = pd.concat([rows[["trade_date", "group", "nav"]], ls_nav[["trade_date", "group", "nav"]]], ignore_index=True)
    return rows[["trade_date", "group", "nav"]]


def top_quantile_turnover(values: pd.DataFrame, quantile: float = 0.2) -> pd.DataFrame:
    previous: set[str] | None = None
    rows = []
    for trade_date, part in values.dropna(subset=["factor_score"]).sort_values("trade_date").groupby("trade_date"):
        count = max(1, int(len(part) * quantile))
        current = set(part.nlargest(count, "factor_score")["order_book_id"].astype(str))
        turnover = None if previous is None or not previous else 1.0 - len(current & previous) / len(previous)
        rows.append({"trade_date": trade_date, "top_count": len(current), "turnover": turnover})
        previous = current
    return pd.DataFrame(rows)

