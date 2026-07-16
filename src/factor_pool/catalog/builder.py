from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

import pandas as pd

from factor_pool.catalog.normalize import normalize_records
from factor_pool.config import CatalogConfig


REQUIRED_COLUMNS = [
    "snapshot_id",
    "vendor_field_name",
    "vendor_category",
    "field_role",
    "data_type",
    "frequency",
    "unit",
    "period_variant",
    "point_in_time_status",
    "classification_status",
    "classification_reason",
    "classification_rule_id",
    "discovered_at",
    "rqdatac_version",
]
_PERIOD_SUFFIX = re.compile(r"_(ttm\d*(?:_\d+)?|lyr(?:_\d+)?|mrq(?:_\d+)?)$", re.IGNORECASE)


def build_catalog(
    records: Iterable[Mapping[str, object]],
    *,
    snapshot_id: str,
    discovered_at: str,
    rqdatac_version: str,
    config: CatalogConfig,
) -> pd.DataFrame:
    rows = []
    for record in normalize_records(records):
        category = record["vendor_category"]
        rule = config.category_rules.get(category)
        if rule is None:
            role, status, rule_id = "unclassified", "quarantined", "fallback.unknown_category"
        else:
            role, status, rule_id = rule.field_role, rule.classification_status, rule.rule_id
        name = record["vendor_field_name"]
        match = _PERIOD_SUFFIX.search(name)
        rows.append({
            "snapshot_id": snapshot_id,
            "vendor_field_name": name,
            "vendor_category": category,
            "field_role": role,
            "data_type": None,
            "frequency": None,
            "unit": None,
            "period_variant": match.group(1).lower() if match else None,
            "point_in_time_status": "pending",
            "classification_status": status,
            "classification_reason": f"RQData vendor category '{category}' mapped by rule {rule_id}",
            "classification_rule_id": rule_id,
            "discovered_at": discovered_at,
            "rqdatac_version": rqdatac_version,
        })
    return pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
