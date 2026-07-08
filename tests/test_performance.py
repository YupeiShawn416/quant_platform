import pandas as pd

from rq_platform.metrics import calculate_performance_metrics


def test_total_return_and_max_drawdown():
    nav = pd.DataFrame(
        {
            "trade_date": ["2025-01-02", "2025-01-03", "2025-01-06"],
            "strategy_nav": [1.0, 1.2, 0.9],
            "benchmark_nav": [1.0, 1.1, 1.0],
        }
    )

    metrics = calculate_performance_metrics(nav)

    assert round(metrics["total_return"], 6) == -0.1
    assert round(metrics["max_drawdown"], 6) == -0.25
    assert round(metrics["benchmark_return"], 6) == 0
    assert round(metrics["excess_return"], 6) == -0.1


def test_empty_nav_does_not_crash():
    metrics = calculate_performance_metrics(pd.DataFrame())

    assert metrics["total_return"] is None
    assert metrics["max_drawdown"] is None


def test_missing_benchmark_is_allowed():
    nav = pd.DataFrame({"trade_date": ["2025-01-02", "2025-01-03"], "strategy_nav": [1.0, 1.1]})

    metrics = calculate_performance_metrics(nav)

    assert round(metrics["total_return"], 6) == 0.1
    assert metrics["benchmark_return"] is None
