from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping

from factor_pool.catalog.builder import build_catalog
from factor_pool.catalog.normalize import catalog_sha256, normalize_records
from factor_pool.config import CatalogConfig
from factor_pool.storage.snapshot_store import persist_snapshot


@dataclass(frozen=True)
class SnapshotResult:
    manifest: dict[str, object]
    output_dir: Path


def build_catalog_snapshot(
    *,
    adapter,
    config: CatalogConfig,
    now: datetime | None = None,
    expected_count: int | None = None,
    expected_hash: str | None = None,
    expected_category_counts: Mapping[str, int] | None = None,
) -> SnapshotResult:
    generated_at = (now or datetime.now().astimezone()).astimezone()
    records = normalize_records(adapter.enumerate_fields(config.categories))
    catalog_hash = catalog_sha256(records)
    snapshot_id = f"rqdata-{config.market}-{generated_at.strftime('%Y%m%dT%H%M%S')}-{catalog_hash[:8]}"
    frame = build_catalog(
        records,
        snapshot_id=snapshot_id,
        discovered_at=generated_at.isoformat(timespec="seconds"),
        rqdatac_version=adapter.sdk_version,
        config=config,
    )
    role_counts = _counts(frame, "field_role")
    category_counts = _counts(frame, "vendor_category")
    status_counts = _counts(frame, "classification_status")
    deviations = []
    if expected_count is not None and len(frame) != expected_count:
        deviations.append({"metric": "field_count", "expected": expected_count, "actual": len(frame)})
    if expected_hash is not None and catalog_hash != expected_hash:
        deviations.append({"metric": "catalog_sha256", "expected": expected_hash, "actual": catalog_hash})
    if expected_category_counts is not None and role_counts != dict(expected_category_counts):
        deviations.append({"metric": "role_counts", "expected": dict(expected_category_counts), "actual": role_counts})

    manifest: dict[str, object] = {
        "snapshot_id": snapshot_id,
        "created_at": generated_at.isoformat(timespec="seconds"),
        "provider": "RQData",
        "market": config.market,
        "rqdatac_version": adapter.sdk_version,
        "field_count": int(len(frame)),
        "catalog_sha256": catalog_hash,
        "vendor_category_counts": category_counts,
        "role_counts": role_counts,
        "classification_status_counts": status_counts,
        "classification_rule_version": config.rule_version,
        "classification_rule_hash": _classification_rule_hash(config),
        "recipe_set_hash": None,
        "deviations": deviations,
        "status": "matched" if not deviations else "changed",
    }
    output_dir = persist_snapshot(frame, manifest=manifest, config=config)
    return SnapshotResult(manifest=manifest, output_dir=output_dir)


def _counts(frame, column: str) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in sorted(frame[column].value_counts().items(), key=lambda item: str(item[0]))
    }


def _classification_rule_hash(config: CatalogConfig) -> str:
    payload = {
        "rule_version": config.rule_version,
        "categories": {
            name: {
                "field_role": rule.field_role,
                "classification_status": rule.classification_status,
                "rule_id": rule.rule_id,
            }
            for name, rule in config.category_rules.items()
        },
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
