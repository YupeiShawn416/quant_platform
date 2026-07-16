import json
import hashlib
from datetime import datetime, timezone

import pandas as pd
import pytest

from factor_pool.config import CatalogConfig, CategoryRule
from factor_pool.storage.snapshot_store import persist_snapshot, validate_snapshot
from factor_pool.workflow import build_catalog_snapshot


def _config(tmp_path):
    return CatalogConfig(
        rule_version="test",
        market="cn",
        output_root=tmp_path / "catalog",
        manifest_root=tmp_path / "manifests",
        category_rules={
            "income_statement": CategoryRule("statement_field", "source_only", "statement"),
            "eod_indicator": CategoryRule("vendor_factor", "candidate_factor", "vendor"),
            "other": CategoryRule("unclassified", "quarantined", "other"),
        },
    )


class FakeAdapter:
    sdk_version = "3.5.5-test"
    market = "cn"

    def enumerate_fields(self, categories):
        values = {
            "income_statement": ["revenue"],
            "eod_indicator": ["pe_ratio_ttm"],
            "other": ["legacy_metric"],
        }
        return [
            {"vendor_field_name": name, "vendor_category": category}
            for category in categories
            for name in values[category]
        ]


def test_persist_snapshot_writes_validated_catalog_and_safe_manifest(tmp_path):
    config = _config(tmp_path)
    frame = pd.DataFrame([
        {
            "snapshot_id": "snapshot-test",
            "vendor_field_name": "legacy_metric",
            "vendor_category": "other",
            "field_role": "unclassified",
            "data_type": None,
            "frequency": None,
            "unit": None,
            "period_variant": None,
            "point_in_time_status": "pending",
            "classification_status": "quarantined",
            "classification_reason": "test",
            "classification_rule_id": "other",
            "discovered_at": "2026-07-16T00:00:00+00:00",
            "rqdatac_version": "3.5.5-test",
        }
    ])
    manifest = {
        "snapshot_id": "snapshot-test",
        "field_count": 1,
        "catalog_sha256": hashlib.sha256(b"legacy_metric").hexdigest(),
        "status": "changed",
    }

    output = persist_snapshot(frame, manifest=manifest, config=config)

    assert output == config.output_root / "snapshot-test"
    assert (output / "source_fields.parquet").is_file()
    assert (output / "quarantined_fields.parquet").is_file()
    assert (output / "classification_summary.json").is_file()
    assert validate_snapshot(output)["field_count"] == 1
    public = json.loads((config.manifest_root / "snapshot-test.json").read_text(encoding="utf-8"))
    assert public == manifest


def test_validate_snapshot_rejects_catalog_hash_mismatch(tmp_path):
    config = _config(tmp_path)
    frame = pd.DataFrame([{
        "snapshot_id": "snapshot-test",
        "vendor_field_name": "legacy_metric",
        "vendor_category": "other",
        "field_role": "unclassified",
        "data_type": None,
        "frequency": None,
        "unit": None,
        "period_variant": None,
        "point_in_time_status": "pending",
        "classification_status": "quarantined",
        "classification_reason": "test",
        "classification_rule_id": "other",
        "discovered_at": "2026-07-16T00:00:00+00:00",
        "rqdatac_version": "3.5.5-test",
    }])
    manifest = {
        "snapshot_id": "snapshot-test",
        "field_count": 1,
        "catalog_sha256": hashlib.sha256(b"legacy_metric").hexdigest(),
        "status": "matched",
    }
    output = persist_snapshot(frame, manifest=manifest, config=config)
    tampered = pd.read_parquet(output / "source_fields.parquet")
    tampered.loc[0, "vendor_field_name"] = "tampered"
    tampered.to_parquet(output / "source_fields.parquet", index=False)

    with pytest.raises(ValueError, match="hash"):
        validate_snapshot(output)


def test_build_catalog_snapshot_reports_counts_hash_and_drift(tmp_path):
    result = build_catalog_snapshot(
        adapter=FakeAdapter(),
        config=_config(tmp_path),
        now=datetime(2026, 7, 16, tzinfo=timezone.utc),
        expected_count=3,
        expected_hash=None,
        expected_category_counts={"statement_field": 1, "vendor_factor": 1, "unclassified": 1},
    )

    assert result.manifest["status"] == "matched"
    assert result.manifest["field_count"] == 3
    assert result.manifest["role_counts"] == {
        "statement_field": 1,
        "unclassified": 1,
        "vendor_factor": 1,
    }
    assert len(result.manifest["catalog_sha256"]) == 64
    assert result.output_dir.is_dir()
