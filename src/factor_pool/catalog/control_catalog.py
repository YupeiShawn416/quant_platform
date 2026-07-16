from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

from factor_pool.config import PROJECT_ROOT
from factor_pool.contracts.models import ControlFieldDefinition
from factor_pool.contracts.status import PitStatus


DEFAULT_CONTROL_CONFIG = PROJECT_ROOT / "configs" / "factor_pool" / "control_fields.yaml"


def load_control_definitions(path: Path | None = None) -> list[ControlFieldDefinition]:
    config_path = (path or DEFAULT_CONTROL_CONFIG).resolve()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    definitions = []
    for item in raw["controls"]:
        definitions.append(ControlFieldDefinition(
            control_id=str(item["control_id"]),
            control_version=str(item["control_version"]),
            field_role=str(item["field_role"]),
            provider=str(item["provider"]),
            source_dataset=str(item["source_dataset"]),
            source_field=str(item["source_field"]),
            availability_rule=str(item["availability_rule"]),
            definition_status=str(item.get("definition_status", "pending")),
            pit_status=PitStatus(str(item.get("pit_status", "pending"))),
            applicable_universe=str(item.get("applicable_universe", "cn_equity")),
            metadata=dict(item.get("metadata", {})),
        ))
    return definitions


def build_control_catalog(
    definitions: Iterable[ControlFieldDefinition],
    *,
    snapshot_id: str,
    created_at: datetime,
) -> pd.DataFrame:
    if created_at.tzinfo is None:
        raise ValueError("created_at must be timezone-aware")
    items = list(definitions)
    ids = [item.control_id for item in items]
    duplicates = sorted({control_id for control_id in ids if ids.count(control_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate control_id: {', '.join(duplicates)}")
    rows = []
    for item in sorted(items, key=lambda value: value.control_id):
        payload = {
            "control_id": item.control_id,
            "control_version": item.control_version,
            "field_role": item.field_role,
            "provider": item.provider,
            "source_dataset": item.source_dataset,
            "source_field": item.source_field,
            "availability_rule": item.availability_rule,
            "definition_status": item.definition_status,
            "pit_status": item.pit_status.value,
            "applicable_universe": item.applicable_universe,
            "metadata": item.metadata,
        }
        rows.append({
            "snapshot_id": snapshot_id,
            **payload,
            "eligible_for_model": False,
            "created_at": created_at.isoformat(timespec="seconds"),
            "code_hash": hashlib.sha256(
                json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
        })
    return pd.DataFrame(rows)


def assert_controls_not_features(control_ids: Iterable[str], feature_ids: Iterable[str]) -> None:
    leaked = sorted(set(control_ids) & set(feature_ids))
    if leaked:
        raise ValueError(f"control fields leaked into model features: {', '.join(leaked)}")
