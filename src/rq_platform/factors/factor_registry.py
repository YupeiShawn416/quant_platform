from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rq_platform.factors.factor_definitions import BUILTIN_FACTORS, FactorDefinition
from rq_platform.settings import settings


class FactorRegistry:
    def __init__(self, registry_path: str | Path | None = None):
        self.registry_path = (
            Path(registry_path).resolve()
            if registry_path is not None
            else settings.factor_library_dir_path / "registry" / "factor_registry.json"
        )

    def list_factors(
        self,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = [item.to_dict() for item in BUILTIN_FACTORS.values()]
        if category:
            rows = [row for row in rows if row["category"] == category]
        if keyword:
            needle = keyword.lower()
            rows = [
                row
                for row in rows
                if needle in row["factor_id"].lower()
                or needle in row["name"].lower()
                or needle in row["description"].lower()
            ]
        return sorted(rows, key=lambda row: row["factor_id"])

    def get(self, factor_id: str) -> FactorDefinition:
        try:
            return BUILTIN_FACTORS[factor_id]
        except KeyError as exc:
            raise KeyError(f"unknown factor_id: {factor_id}") from exc

    def write_registry(self) -> Path:
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps(self.list_factors(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return self.registry_path

