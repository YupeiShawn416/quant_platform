from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import yaml

from factor_pool.config import PROJECT_ROOT


REQUIRED_COLUMNS = {
    "signal_date",
    "order_book_id",
    "vendor_field_name",
    "value",
    "industry_code",
    "universe_member",
}
DEFAULT_HEALTH_CONFIG = PROJECT_ROOT / "configs" / "factor_pool" / "ingredient_health.yaml"


@dataclass(frozen=True)
class IngredientHealthConfig:
    rule_version: str
    preferred_coverage: float
    specialized_coverage: float
    sparse_coverage: float
    annual_coverage: float
    preferred_years: int
    specialized_years: int
    minimum_history_years: int
    minimum_quarters_per_year: int
    industry_system: str
    industry_level: int

    def __post_init__(self) -> None:
        for name in ("preferred_coverage", "specialized_coverage", "sparse_coverage", "annual_coverage"):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between 0 and 1")
        if self.sparse_coverage >= self.preferred_coverage:
            raise ValueError("sparse_coverage must be below preferred_coverage")
        for name in ("preferred_years", "specialized_years", "minimum_history_years", "minimum_quarters_per_year"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be positive")

    @property
    def snapshot_id(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def load_ingredient_health_config(path: Path | None = None) -> IngredientHealthConfig:
    raw = yaml.safe_load((path or DEFAULT_HEALTH_CONFIG).read_text(encoding="utf-8"))
    names = {
        "rule_version", "preferred_coverage", "specialized_coverage", "sparse_coverage",
        "annual_coverage", "preferred_years", "specialized_years", "minimum_history_years",
        "minimum_quarters_per_year", "industry_system", "industry_level",
    }
    return IngredientHealthConfig(**{name: raw[name] for name in names})


def evaluate_ingredient_health(
    observations: pd.DataFrame,
    config: IngredientHealthConfig,
) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(observations.columns)
    if missing:
        raise ValueError(f"ingredient observations missing columns: {', '.join(sorted(missing))}")
    frame = observations.loc[observations["universe_member"].fillna(False)].copy()
    if frame.empty:
        raise ValueError("ingredient observations contain no dynamic-universe members")
    frame["signal_date"] = pd.to_datetime(frame["signal_date"], errors="raise")
    if frame.duplicated(["signal_date", "order_book_id", "vendor_field_name"]).any():
        raise ValueError("ingredient observations contain duplicate primary keys")
    frame["is_valid"] = frame["value"].notna()
    frame["year"] = frame["signal_date"].dt.year

    rows = []
    for field_name, part in frame.groupby("vendor_field_name", sort=True):
        expected = len(part)
        valid = int(part["is_valid"].sum())
        coverage = valid / expected
        valid_part = part.loc[part["is_valid"]]
        first_date = valid_part["signal_date"].min() if valid else pd.NaT
        usable_years = _usable_year_count(part, config)
        industry_coverage = _industry_coverage(part)
        best_industry, best_industry_coverage = _best_industry(industry_coverage)
        concentration = _industry_concentration(valid_part)
        density_since_first = _coverage_since_first(part, first_date)
        status, applicable = _status(
            coverage=coverage,
            usable_years=usable_years,
            density_since_first=density_since_first,
            best_industry=best_industry,
            best_industry_coverage=best_industry_coverage,
            config=config,
        )
        rows.append({
            "vendor_field_name": str(field_name),
            "first_available_date": first_date.strftime("%Y-%m-%d") if pd.notna(first_date) else None,
            "coverage_rate": float(coverage),
            "coverage_scope": "csi500_dynamic_quarter_end",
            "usable_year_count": int(usable_years),
            "industry_concentration": float(concentration),
            "applicable_universe": applicable,
            "ingredient_status": status,
            "quality_snapshot_id": config.snapshot_id,
        })
    return pd.DataFrame(rows)


def _usable_year_count(part: pd.DataFrame, config: IngredientHealthConfig) -> int:
    usable = 0
    for _, year in part.groupby("year"):
        valid_quarters = year.loc[year["is_valid"], "signal_date"].dt.quarter.nunique()
        if valid_quarters >= config.minimum_quarters_per_year and year["is_valid"].mean() >= config.annual_coverage:
            usable += 1
    return usable


def _industry_coverage(part: pd.DataFrame) -> dict[str, float]:
    return {
        str(industry): float(group["is_valid"].mean())
        for industry, group in part.dropna(subset=["industry_code"]).groupby("industry_code")
    }


def _best_industry(coverage: dict[str, float]) -> tuple[str | None, float]:
    if not coverage:
        return None, 0.0
    return max(coverage.items(), key=lambda item: (item[1], item[0]))


def _industry_concentration(valid_part: pd.DataFrame) -> float:
    counts = valid_part["industry_code"].dropna().value_counts()
    return float(counts.iloc[0] / counts.sum()) if not counts.empty else 0.0


def _coverage_since_first(part: pd.DataFrame, first_date: pd.Timestamp) -> float:
    if pd.isna(first_date):
        return 0.0
    active = part.loc[part["signal_date"] >= first_date]
    return float(active["is_valid"].mean())


def _status(
    *,
    coverage: float,
    usable_years: int,
    density_since_first: float,
    best_industry: str | None,
    best_industry_coverage: float,
    config: IngredientHealthConfig,
) -> tuple[str, str]:
    if usable_years < config.minimum_history_years and density_since_first >= config.annual_coverage:
        return "insufficient_history", "csi500_dynamic"
    if coverage >= config.preferred_coverage and usable_years >= config.preferred_years:
        return "preferred", "csi500_dynamic"
    if best_industry is not None and best_industry_coverage >= config.specialized_coverage and usable_years >= config.specialized_years:
        return "specialized", f"{config.industry_system}_l{config.industry_level}:{best_industry}"
    if coverage < config.sparse_coverage and best_industry_coverage < config.specialized_coverage:
        return "sparse", "csi500_dynamic"
    return "pending_review", "csi500_dynamic"
