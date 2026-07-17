from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Protocol, Sequence

import pandas as pd


class IngredientProvider(Protocol):
    def values(self, ids: list[str], fields: list[str], date: str) -> pd.DataFrame: ...


class RQDataIngredientProvider:
    def __init__(self, sdk) -> None:
        self.sdk = sdk

    def values(self, ids: list[str], fields: list[str], date: str) -> pd.DataFrame:
        frame = pd.DataFrame(self.sdk.get_factor(
            ids, fields, start_date=date, end_date=date, expect_df=True,
        ))
        if isinstance(frame.index, pd.MultiIndex):
            frame = frame.reset_index().set_index("order_book_id")
            frame = frame.drop(columns=["date"], errors="ignore")
        frame.index = frame.index.astype(str)
        return frame.reindex(index=ids, columns=fields)


def backfill_ingredient_values(
    provider: IngredientProvider,
    *,
    controls: pd.DataFrame,
    fields: Sequence[str],
    signal_date: str,
    output_root: Path,
    chunk_size: int = 500,
) -> dict[str, int]:
    if chunk_size < 1:
        raise ValueError("chunk_size must be positive")
    ids = controls["order_book_id"].astype(str).tolist()
    if not ids or controls["order_book_id"].duplicated().any():
        raise ValueError("controls must contain unique universe members")
    date_dir = output_root / f"date={signal_date}"
    date_dir.mkdir(parents=True, exist_ok=True)
    result = {"written": 0, "cached": 0, "failed": 0, "cells": 0}
    for offset in range(0, len(fields), chunk_size):
        chunk = list(fields[offset:offset + chunk_size])
        digest = hashlib.sha256("\n".join(chunk).encode()).hexdigest()[:16]
        final_file = date_dir / f"fields={offset:05d}-{digest}.parquet"
        result["cells"] += len(ids) * len(chunk)
        if final_file.is_file():
            result["cached"] += 1
            continue
        temp_file = final_file.with_suffix(f".tmp-{os.getpid()}.parquet")
        try:
            frame = provider.values(ids, chunk, signal_date)
            if frame.shape != (len(ids), len(chunk)):
                raise ValueError(f"ingredient response shape mismatch: {frame.shape}")
            frame.index.name = "order_book_id"
            frame.reset_index().to_parquet(temp_file, index=False)
            if pd.read_parquet(temp_file).shape != (len(ids), len(chunk) + 1):
                raise ValueError("persisted ingredient shape mismatch")
            temp_file.replace(final_file)
            result["written"] += 1
        except Exception:
            result["failed"] += 1
            temp_file.unlink(missing_ok=True)
            raise
    return result
