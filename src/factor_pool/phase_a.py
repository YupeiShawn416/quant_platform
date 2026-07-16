from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Mapping

import pandas as pd

from factor_pool.audit.ingredient_health import IngredientHealthConfig, evaluate_ingredient_health
from factor_pool.audit.vendor_factor import VendorAuditConfig, audit_vendor_candidates
from factor_pool.catalog.control_catalog import build_control_catalog, load_control_definitions


def build_phase_a_assets(
    source_catalog: pd.DataFrame,
    *,
    ingredient_observations: pd.DataFrame,
    definitions: Mapping[str, str],
    event_observations: pd.DataFrame,
    technical_observations: pd.DataFrame,
    health_config: IngredientHealthConfig,
    snapshot_id: str,
    created_at: datetime,
) -> tuple[dict[str, pd.DataFrame], dict[str, object]]:
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    required = {"vendor_field_name", "vendor_category", "field_role", "classification_status"}
    missing = required - set(source_catalog.columns)
    if missing:
        raise ValueError(f"source catalog missing columns: {', '.join(sorted(missing))}")

    statement = source_catalog.loc[source_catalog["field_role"] == "statement_field"].copy()
    candidates = source_catalog.loc[source_catalog["classification_status"] == "candidate_factor"].copy()
    quarantine = source_catalog.loc[source_catalog["classification_status"] == "quarantined"].copy()

    health = _ingredient_health_for_all(statement, ingredient_observations, health_config)
    controls = build_control_catalog(
        load_control_definitions(), snapshot_id=snapshot_id, created_at=created_at
    )
    vendor_audit = audit_vendor_candidates(
        candidates,
        definitions=definitions,
        event_observations=event_observations,
        technical_observations=technical_observations,
        config=VendorAuditConfig(rule_version="1.1.0"),
    )
    triage = _triage_quarantine(quarantine)
    assets = {
        "ingredient_health": health,
        "control_fields": controls,
        "vendor_factor_audit": vendor_audit,
        "quarantine_triage": triage,
    }
    ingredient_pending = int(health["ingredient_status"].eq("pending_review").sum())
    vendor_pending = int(vendor_audit["pit_status"].isin(["pending", "documentation_passed"]).sum())
    control_pending = int((~controls["pit_status"].isin(["verified", "not_applicable"])).sum())
    passthrough_count = int(
        (
            vendor_audit["definition_status"].eq("definition_verified")
            & vendor_audit["pit_status"].isin(["sample_alignment_passed", "verified"])
        ).sum()
    )
    manifest: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "created_at": created_at.isoformat(timespec="seconds"),
        "source_field_count": int(len(source_catalog)),
        "statement_field_count": int(len(statement)),
        "vendor_candidate_count": int(len(candidates)),
        "quarantine_input_count": int(len(quarantine)),
        "control_field_count": int(len(controls)),
        "ingredient_pending_count": ingredient_pending,
        "vendor_pit_pending_count": vendor_pending,
        "control_pending_count": control_pending,
        "vendor_passthrough_recipe_count": passthrough_count,
        "auto_eligible_count": int(vendor_audit["eligible_for_model"].astype(bool).sum()),
        "asset_counts": {name: int(len(frame)) for name, frame in assets.items()},
        "asset_sha256": {name: _frame_hash(frame) for name, frame in assets.items()},
        "status": "complete" if ingredient_pending == 0 and vendor_pending == 0 and control_pending == 0 else "incomplete",
    }
    return assets, manifest


def _ingredient_health_for_all(
    statement: pd.DataFrame,
    observations: pd.DataFrame,
    config: IngredientHealthConfig,
) -> pd.DataFrame:
    names = statement["vendor_field_name"].astype(str).sort_values().tolist()
    if observations.empty:
        evaluated = pd.DataFrame(columns=[
            "vendor_field_name", "first_available_date", "coverage_rate", "coverage_scope",
            "usable_year_count", "industry_concentration", "applicable_universe",
            "ingredient_status", "quality_snapshot_id",
        ])
    else:
        evaluated = evaluate_ingredient_health(observations, config)
    indexed = evaluated.set_index("vendor_field_name") if not evaluated.empty else pd.DataFrame().rename_axis("vendor_field_name")
    rows = []
    for name in names:
        if name in indexed.index:
            row = indexed.loc[name].to_dict()
            row["vendor_field_name"] = name
        else:
            row = {
                "vendor_field_name": name,
                "first_available_date": None,
                "coverage_rate": None,
                "coverage_scope": "csi500_dynamic_quarter_end",
                "usable_year_count": 0,
                "industry_concentration": None,
                "applicable_universe": "csi500_dynamic",
                "ingredient_status": "pending_review",
                "quality_snapshot_id": config.snapshot_id,
            }
        rows.append(row)
    return pd.DataFrame(rows)


def _triage_quarantine(quarantine: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for item in quarantine.sort_values("vendor_field_name").itertuples(index=False):
        name = str(item.vendor_field_name)
        lower = name.lower()
        if re.search(r"_(?:ttm|lyr|mrq)\d*_[0-9]+$", lower):
            triage_class, reason = "financial_period_variant", "recognized multi-period financial suffix"
        elif any(token in lower for token in ("market_val", "industry", "suspend", "limit_up", "limit_down", "is_st")):
            triage_class, reason = "control_candidate", "name indicates a possible control or exposure"
        elif name.isupper() and len(name) <= 32:
            triage_class, reason = "technical_alias", "uppercase compact name resembles a technical indicator alias"
        else:
            triage_class, reason = "unresolved", "no deterministic promotion rule matched"
        rows.append({
            "vendor_field_name": name,
            "vendor_category": str(item.vendor_category),
            "triage_class": triage_class,
            "triage_reason": reason,
            "classification_status": "quarantined",
            "eligible_for_model": False,
        })
    return pd.DataFrame(rows)


def _frame_hash(frame: pd.DataFrame) -> str:
    canonical = frame.sort_index(axis=1).to_json(orient="records", date_format="iso", force_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
