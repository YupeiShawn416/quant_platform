from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from rq_platform.settings import settings


class FactorFileNotFound(FileNotFoundError):
    pass


class FactorStore:
    def __init__(self, root: str | Path | None = None):
        self.root = Path(root).resolve() if root is not None else settings.factor_library_dir_path

    def values_dir(self, factor_id: str) -> Path:
        return self.root / "values" / factor_id

    def analysis_dir(self, factor_id: str) -> Path:
        return self.root / "analysis" / factor_id

    def write_values(self, factor_id: str, frame: pd.DataFrame, overwrite: bool = True) -> list[Path]:
        required = {"trade_date", "order_book_id", "factor_value", "factor_score"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"factor values missing columns: {', '.join(sorted(missing))}")
        output_paths: list[Path] = []
        clean = frame.copy()
        clean["trade_date"] = pd.to_datetime(clean["trade_date"]).dt.strftime("%Y-%m-%d")
        clean = clean.drop_duplicates(["trade_date", "order_book_id"]).sort_values(["trade_date", "order_book_id"])
        for year, part in clean.groupby(clean["trade_date"].str[:4]):
            year_dir = self.values_dir(factor_id) / f"year={year}"
            year_dir.mkdir(parents=True, exist_ok=True)
            path = year_dir / "factor_values.parquet"
            if path.exists() and not overwrite:
                existing = pd.read_parquet(path)
                part = (
                    pd.concat([existing, part], ignore_index=True)
                    .drop_duplicates(["trade_date", "order_book_id"], keep="last")
                    .sort_values(["trade_date", "order_book_id"])
                )
            part.to_parquet(path, index=False)
            output_paths.append(path)
        return output_paths

    def read_values(
        self,
        factor_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        files = sorted(self.values_dir(factor_id).glob("year=*/factor_values.parquet"))
        if not files:
            raise FactorFileNotFound(f"factor values not found: {factor_id}")
        frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
        frame["trade_date"] = pd.to_datetime(frame["trade_date"]).dt.strftime("%Y-%m-%d")
        if start_date:
            frame = frame[frame["trade_date"] >= start_date]
        if end_date:
            frame = frame[frame["trade_date"] <= end_date]
        return frame.sort_values(["trade_date", "order_book_id"]).reset_index(drop=True)

    def write_analysis(self, factor_id: str, files: dict[str, Any]) -> Path:
        directory = self.analysis_dir(factor_id)
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in files.items():
            path = directory / name
            if isinstance(value, pd.DataFrame):
                value.to_csv(path, index=False)
            elif name.endswith(".json"):
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            else:
                path.write_text(str(value), encoding="utf-8")
        return directory

    def read_analysis_json(self, factor_id: str, filename: str = "factor_summary.json") -> dict[str, Any]:
        path = self.analysis_dir(factor_id) / filename
        if not path.exists():
            raise FactorFileNotFound(f"factor analysis not found: {factor_id}/{filename}")
        return json.loads(path.read_text(encoding="utf-8"))

    def read_analysis_csv(self, factor_id: str, filename: str) -> pd.DataFrame:
        path = self.analysis_dir(factor_id) / filename
        if not path.exists():
            raise FactorFileNotFound(f"factor analysis not found: {factor_id}/{filename}")
        return pd.read_csv(path)

