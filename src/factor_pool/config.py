from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "factor_pool" / "catalog.yaml"


@dataclass(frozen=True)
class CategoryRule:
    field_role: str
    classification_status: str
    rule_id: str


@dataclass(frozen=True)
class CatalogConfig:
    rule_version: str
    market: str
    output_root: Path
    manifest_root: Path
    category_rules: dict[str, CategoryRule]

    @property
    def category_roles(self) -> dict[str, tuple[str, str]]:
        return {
            name: (rule.field_role, rule.classification_status)
            for name, rule in self.category_rules.items()
        }

    @property
    def categories(self) -> tuple[str, ...]:
        return tuple(self.category_rules)


def load_catalog_config(path: Path | None = None) -> CatalogConfig:
    config_path = (path or DEFAULT_CONFIG_PATH).resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    rules = {
        name: CategoryRule(
            field_role=value["field_role"],
            classification_status=value["classification_status"],
            rule_id=value["rule_id"],
        )
        for name, value in raw["categories"].items()
    }
    return CatalogConfig(
        rule_version=str(raw["rule_version"]),
        market=str(raw["market"]),
        output_root=_resolve_project_path(raw["output_root"]),
        manifest_root=_resolve_project_path(raw["manifest_root"]),
        category_rules=rules,
    )


def _resolve_project_path(value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else PROJECT_ROOT / path).resolve()

