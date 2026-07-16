from datetime import datetime, timezone

import pandas as pd

from factor_pool.audit.ingredient_health import IngredientHealthConfig
from factor_pool.config import load_catalog_config
from factor_pool.phase_a import build_phase_a_assets
from factor_pool.storage.snapshot_store import persist_phase_a_assets


def test_phase_a_assets_keep_missing_live_audits_pending_and_never_auto_eligible(tmp_path):
    source = pd.DataFrame([
        _source("revenue", "income_statement", "statement_field", "source_only"),
        _source("pe_ratio_ttm", "eod_indicator", "vendor_factor", "candidate_factor"),
        _source("old_metric_ttm1_0", "other", "unclassified", "quarantined"),
    ])
    assets, manifest = build_phase_a_assets(
        source,
        ingredient_observations=pd.DataFrame(),
        definitions={},
        event_observations=pd.DataFrame(),
        technical_observations=pd.DataFrame(),
        health_config=_health_config(),
        snapshot_id="phase-a-test",
        created_at=datetime(2026, 7, 16, tzinfo=timezone.utc),
    )

    assert manifest["status"] == "incomplete"
    assert manifest["ingredient_pending_count"] == 1
    assert manifest["vendor_pit_pending_count"] == 1
    assert assets["ingredient_health"].iloc[0]["ingredient_status"] == "pending_review"
    assert assets["vendor_factor_audit"]["eligible_for_model"].eq(False).all()
    assert assets["quarantine_triage"].iloc[0]["triage_class"] == "financial_period_variant"
    assert len(assets["control_fields"]) == 8

    output = persist_phase_a_assets(
        assets,
        manifest=manifest,
        output_root=tmp_path / "phase_a",
        public_manifest_root=tmp_path / "manifests",
    )
    assert (output / "ingredient_health.parquet").is_file()
    assert (output / "control_fields.parquet").is_file()
    assert (output / "vendor_factor_audit.parquet").is_file()
    assert (output / "quarantine_triage.parquet").is_file()


def _source(name, category, role, status):
    return {
        "vendor_field_name": name,
        "vendor_category": category,
        "field_role": role,
        "classification_status": status,
    }


def _health_config():
    return IngredientHealthConfig(
        rule_version="test",
        preferred_coverage=0.8,
        specialized_coverage=0.8,
        sparse_coverage=0.2,
        annual_coverage=0.5,
        preferred_years=2,
        specialized_years=2,
        minimum_history_years=2,
        minimum_quarters_per_year=3,
        industry_system="citics_2019",
        industry_level=1,
    )
