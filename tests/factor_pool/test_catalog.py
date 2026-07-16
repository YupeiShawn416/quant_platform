import hashlib

from factor_pool.catalog.builder import build_catalog
from factor_pool.catalog.normalize import catalog_sha256, normalize_records
from factor_pool.config import load_catalog_config


def test_normalize_records_deduplicates_and_sorts_stably():
    records = normalize_records([
        {"vendor_field_name": " beta ", "vendor_category": "other"},
        {"vendor_field_name": "alpha", "vendor_category": "income_statement"},
        {"vendor_field_name": "beta", "vendor_category": "other"},
    ])

    assert records == [
        {"vendor_field_name": "alpha", "vendor_category": "income_statement"},
        {"vendor_field_name": "beta", "vendor_category": "other"},
    ]
    assert catalog_sha256(records) == hashlib.sha256(b"alpha\nbeta").hexdigest()


def test_build_catalog_uses_vendor_categories_and_quarantines_unknowns():
    config = load_catalog_config()
    records = [
        {"vendor_field_name": "revenue", "vendor_category": "income_statement"},
        {"vendor_field_name": "pe_ratio_ttm", "vendor_category": "eod_indicator"},
        {"vendor_field_name": "old_metric_ttm1_2", "vendor_category": "other"},
    ]

    frame = build_catalog(
        records,
        snapshot_id="rqdata-cn-test",
        discovered_at="2026-07-16T00:00:00+08:00",
        rqdatac_version="3.5.5",
        config=config,
    )

    keyed = frame.set_index("vendor_field_name")
    assert keyed.loc["revenue", "field_role"] == "statement_field"
    assert keyed.loc["revenue", "classification_status"] == "source_only"
    assert keyed.loc["pe_ratio_ttm", "classification_status"] == "candidate_factor"
    assert keyed.loc["old_metric_ttm1_2", "classification_status"] == "quarantined"
    assert keyed.loc["old_metric_ttm1_2", "period_variant"] == "ttm1_2"
    assert frame["classification_reason"].str.len().gt(0).all()
    assert frame["classification_rule_id"].str.len().gt(0).all()
