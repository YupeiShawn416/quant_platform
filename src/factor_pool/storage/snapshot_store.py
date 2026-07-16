from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from factor_pool.catalog.builder import REQUIRED_COLUMNS
from factor_pool.catalog.normalize import catalog_sha256
from factor_pool.config import CatalogConfig


def persist_snapshot(
    frame: pd.DataFrame,
    *,
    manifest: dict[str, Any],
    config: CatalogConfig,
) -> Path:
    snapshot_id = str(manifest["snapshot_id"])
    _validate_frame(frame, snapshot_id=snapshot_id)
    _validate_catalog_hash(frame, manifest)
    config.output_root.mkdir(parents=True, exist_ok=True)
    final_dir = config.output_root / snapshot_id
    if final_dir.exists():
        raise FileExistsError(f"snapshot already exists: {snapshot_id}")
    temp_dir = config.output_root / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    try:
        temp_dir.mkdir()
        frame.to_parquet(temp_dir / "source_fields.parquet", index=False)
        frame.loc[frame["classification_status"] == "quarantined"].to_parquet(
            temp_dir / "quarantined_fields.parquet", index=False
        )
        summary = {
            "field_count": int(len(frame)),
            "vendor_category_counts": _counts(frame, "vendor_category"),
            "role_counts": _counts(frame, "field_role"),
            "classification_status_counts": _counts(frame, "classification_status"),
        }
        _write_json(temp_dir / "classification_summary.json", summary)
        _write_json(temp_dir / "request_manifest.json", manifest)
        persisted = pd.read_parquet(temp_dir / "source_fields.parquet")
        _validate_frame(persisted, snapshot_id=snapshot_id)
        if len(persisted) != int(manifest["field_count"]):
            raise ValueError("persisted field count differs from manifest")
        _validate_catalog_hash(persisted, manifest)
        temp_dir.replace(final_dir)
    except Exception:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        raise

    config.manifest_root.mkdir(parents=True, exist_ok=True)
    _atomic_write_json(config.manifest_root / f"{snapshot_id}.json", manifest)
    return final_dir


def validate_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    manifest = json.loads((snapshot_dir / "request_manifest.json").read_text(encoding="utf-8"))
    frame = pd.read_parquet(snapshot_dir / "source_fields.parquet")
    _validate_frame(frame, snapshot_id=str(manifest["snapshot_id"]))
    if len(frame) != int(manifest["field_count"]):
        raise ValueError("snapshot row count differs from manifest")
    _validate_catalog_hash(frame, manifest)
    return {
        "snapshot_id": manifest["snapshot_id"],
        "field_count": int(len(frame)),
        "status": manifest["status"],
    }


def _validate_frame(frame: pd.DataFrame, *, snapshot_id: str) -> None:
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"catalog missing required columns: {', '.join(sorted(missing))}")
    if frame.empty:
        raise ValueError("catalog must not be empty")
    if frame["vendor_field_name"].duplicated().any():
        raise ValueError("vendor_field_name must be unique within a snapshot")
    if set(frame["snapshot_id"].astype(str)) != {snapshot_id}:
        raise ValueError("catalog snapshot_id is inconsistent")
    if frame["classification_reason"].isna().any():
        raise ValueError("classification_reason is mandatory")


def _counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in sorted(frame[column].value_counts(dropna=False).items(), key=lambda item: str(item[0]))
    }


def _validate_catalog_hash(frame: pd.DataFrame, manifest: dict[str, Any]) -> None:
    expected = manifest.get("catalog_sha256")
    if expected is None:
        return
    records = [
        {"vendor_field_name": name}
        for name in sorted(frame["vendor_field_name"].astype(str).tolist())
    ]
    actual = catalog_sha256(records)
    if actual != expected:
        raise ValueError("catalog hash differs from manifest")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        _write_json(temp, value)
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()
