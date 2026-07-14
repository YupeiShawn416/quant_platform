from __future__ import annotations

import pandas as pd


def winsorize_by_date(frame: pd.DataFrame, value_col: str = "factor_value", lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    return frame.groupby("trade_date")[value_col].transform(lambda s: s.clip(s.quantile(lower), s.quantile(upper)))


def zscore_by_date(frame: pd.DataFrame, value_col: str = "factor_value") -> pd.Series:
    def _zscore(s: pd.Series) -> pd.Series:
        std = s.std(ddof=0)
        if pd.isna(std) or std == 0:
            return s * 0
        return (s - s.mean()) / std

    return frame.groupby("trade_date")[value_col].transform(_zscore)


def clean_factor_values(frame: pd.DataFrame, lower: float = 0.01, upper: float = 0.99) -> pd.DataFrame:
    output = frame.copy()
    output["factor_value_winsorized"] = winsorize_by_date(output, lower=lower, upper=upper)
    output["factor_score"] = zscore_by_date(output, "factor_value_winsorized")
    return output
