from __future__ import annotations

import pandas as pd


def to_factor_wide(factor_long: pd.DataFrame) -> pd.DataFrame:
    wide = factor_long.pivot_table(
        index=["trade_date", "order_book_id"],
        columns="factor_id",
        values="factor_value",
        aggfunc="last",
    )
    return wide.reset_index().rename_axis(columns=None)
