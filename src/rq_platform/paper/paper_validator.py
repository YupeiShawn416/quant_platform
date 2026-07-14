from __future__ import annotations

from pathlib import Path

import pandas as pd

from rq_platform.data.query_service import SUPPORTED_END_DATE, SUPPORTED_START_DATE
from rq_platform.settings import settings


REQUIRED_WEIGHT_COLUMNS = {"trade_date", "order_book_id", "target_weight"}


class PaperValidationError(ValueError):
    pass


def validate_target_weights(frame: pd.DataFrame, data_root: str | Path | None = None) -> pd.DataFrame:
    missing = sorted(REQUIRED_WEIGHT_COLUMNS - set(frame.columns))
    if missing:
        raise PaperValidationError(f"target weights missing columns: {', '.join(missing)}")
    output = frame[["trade_date", "order_book_id", "target_weight"]].copy()
    output["trade_date"] = pd.to_datetime(output["trade_date"], errors="coerce").dt.strftime("%Y-%m-%d")
    if output["trade_date"].isna().any():
        raise PaperValidationError("trade_date must be YYYY-MM-DD")
    output["order_book_id"] = output["order_book_id"].astype(str).str.strip()
    output["target_weight"] = pd.to_numeric(output["target_weight"], errors="coerce")
    if output["order_book_id"].eq("").any():
        raise PaperValidationError("order_book_id cannot be empty")
    if output["target_weight"].isna().any():
        raise PaperValidationError("target_weight must be numeric")
    if (output["target_weight"] < 0).any():
        raise PaperValidationError("target_weight must be >= 0")
    if output["trade_date"].min() < SUPPORTED_START_DATE or output["trade_date"].max() > SUPPORTED_END_DATE:
        raise PaperValidationError(f"trade_date must be between {SUPPORTED_START_DATE} and {SUPPORTED_END_DATE}")
    duplicated = output.duplicated(["trade_date", "order_book_id"])
    if duplicated.any():
        raise PaperValidationError("duplicate trade_date + order_book_id rows are not allowed")
    weight_sum = output.groupby("trade_date")["target_weight"].sum()
    bad_dates = weight_sum[weight_sum > 1.000001]
    if not bad_dates.empty:
        raise PaperValidationError(f"target weights exceed 1.0 on {bad_dates.index[0]}")
    known = _instrument_ids(data_root)
    unknown = sorted(set(output["order_book_id"]) - known)
    if unknown:
        raise PaperValidationError(f"unknown order_book_id: {unknown[0]}")
    return output.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)


def _instrument_ids(data_root: str | Path | None = None) -> set[str]:
    root = Path(data_root).resolve() if data_root is not None else settings.data_root_path
    path = root / "instruments" / "instruments.parquet"
    if not path.exists():
        raise PaperValidationError("instruments dataset not found")
    frame = pd.read_parquet(path, columns=["order_book_id"])
    return set(frame["order_book_id"].astype(str))
