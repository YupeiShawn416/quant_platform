from __future__ import annotations

import math

import pandas as pd


def calculate_performance_metrics(
    nav_df,
    benchmark_col: str = "benchmark_nav",
    strategy_col: str = "strategy_nav",
    periods_per_year: int = 252,
) -> dict:
    frame = pd.DataFrame(nav_df).copy()
    metrics = {
        "total_return": None,
        "annual_return": None,
        "annual_volatility": None,
        "sharpe": None,
        "max_drawdown": None,
        "benchmark_return": None,
        "excess_return": None,
        "benchmark_annual_return": None,
        "tracking_error": None,
        "information_ratio": None,
        "win_rate": None,
    }
    if frame.empty or strategy_col not in frame.columns:
        return metrics

    strategy_nav = _clean_series(frame[strategy_col])
    if len(strategy_nav) < 2:
        return metrics

    strategy_returns = strategy_nav.pct_change().dropna()
    metrics["total_return"] = _safe_float(strategy_nav.iloc[-1] / strategy_nav.iloc[0] - 1)
    metrics["annual_return"] = _annual_return(strategy_nav, periods_per_year)
    metrics["annual_volatility"] = _annual_volatility(strategy_returns, periods_per_year)
    metrics["sharpe"] = _safe_ratio(metrics["annual_return"], metrics["annual_volatility"])
    metrics["max_drawdown"] = _max_drawdown(strategy_nav)
    metrics["win_rate"] = _safe_float((strategy_returns > 0).mean()) if not strategy_returns.empty else None

    if benchmark_col in frame.columns:
        benchmark_nav = _clean_series(frame[benchmark_col])
        if len(benchmark_nav) >= 2:
            benchmark_returns = benchmark_nav.pct_change().dropna()
            metrics["benchmark_return"] = _safe_float(
                benchmark_nav.iloc[-1] / benchmark_nav.iloc[0] - 1
            )
            metrics["benchmark_annual_return"] = _annual_return(
                benchmark_nav, periods_per_year
            )
            if metrics["total_return"] is not None and metrics["benchmark_return"] is not None:
                metrics["excess_return"] = _safe_float(
                    metrics["total_return"] - metrics["benchmark_return"]
                )
            aligned = pd.concat([strategy_returns, benchmark_returns], axis=1).dropna()
            if not aligned.empty:
                active_returns = aligned.iloc[:, 0] - aligned.iloc[:, 1]
                tracking_error = active_returns.std(ddof=0) * math.sqrt(periods_per_year)
                metrics["tracking_error"] = _safe_float(tracking_error)
                active_annual = active_returns.mean() * periods_per_year
                metrics["information_ratio"] = _safe_ratio(
                    _safe_float(active_annual), metrics["tracking_error"]
                )

    return metrics


def _clean_series(values) -> pd.Series:
    series = pd.to_numeric(pd.Series(values), errors="coerce").dropna()
    return series[series > 0].reset_index(drop=True)


def _annual_return(nav: pd.Series, periods_per_year: int) -> float | None:
    if len(nav) < 2:
        return None
    total_return = nav.iloc[-1] / nav.iloc[0]
    periods = len(nav) - 1
    if periods <= 0:
        return None
    return _safe_float(total_return ** (periods_per_year / periods) - 1)


def _annual_volatility(returns: pd.Series, periods_per_year: int) -> float | None:
    if returns.empty:
        return None
    return _safe_float(returns.std(ddof=0) * math.sqrt(periods_per_year))


def _max_drawdown(nav: pd.Series) -> float | None:
    if nav.empty:
        return None
    drawdown = nav / nav.cummax() - 1
    return _safe_float(drawdown.min())


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return _safe_float(numerator / denominator)


def _safe_float(value) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(result) or math.isinf(result):
        return None
    return result
