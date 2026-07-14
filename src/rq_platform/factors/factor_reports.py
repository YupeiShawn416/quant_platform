from __future__ import annotations

from typing import Any

import pandas as pd


def records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    clean = frame.where(pd.notna(frame), None)
    return clean.to_dict(orient="records")


def public_artifact_path(path: str) -> str:
    parts = path.split("/")
    for marker in ["data", "runs"]:
        if marker in parts:
            return "/".join(parts[parts.index(marker) :])
    return path.split("/")[-1]

