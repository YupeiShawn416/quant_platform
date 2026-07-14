from __future__ import annotations

import pandas as pd


def total_return(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    return float(nav.iloc[-1]) - 1.0


def max_drawdown(nav: pd.Series) -> float:
    if nav.empty:
        return 0.0
    curve = nav.astype(float)
    drawdowns = curve / curve.cummax() - 1.0
    return float(drawdowns.min())
