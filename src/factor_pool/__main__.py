from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd

from factor_pool.audit.ingredient_health import load_ingredient_health_config
from factor_pool.catalog.normalize import normalize_records
from factor_pool.config import CatalogConfig, load_catalog_config
from factor_pool.data_adapter.rqdata import create_adapter_from_environment
from factor_pool.phase_a import build_phase_a_assets
from factor_pool.storage.snapshot_store import persist_phase_a_assets, validate_snapshot
from factor_pool.workflow import build_catalog_snapshot


BASELINE_COUNT = 13_482
BASELINE_HASH = "45d11857ac9cce78946a2a7504ac6ec25cbb70c73764e45cb34ce313b4fbfbe0"
BASELINE_ROLE_COUNTS = {
    "statement_field": 9_858,
    "unclassified": 3_040,
    "vendor_factor": 584,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m factor_pool")
    commands = parser.add_subparsers(dest="command", required=True)

    rqdata = commands.add_parser("rqdata")
    rqdata_commands = rqdata.add_subparsers(dest="rqdata_command", required=True)
    rqdata_commands.add_parser("probe")

    catalog = commands.add_parser("catalog")
    catalog_commands = catalog.add_subparsers(dest="catalog_command", required=True)
    catalog_commands.add_parser("build")
    for name in ("validate", "summarize"):
        command = catalog_commands.add_parser(name)
        command.add_argument("--snapshot", type=Path)

    phase_a = commands.add_parser("phase-a")
    phase_a_commands = phase_a.add_subparsers(dest="phase_a_command", required=True)
    phase_a_run = phase_a_commands.add_parser("run")
    phase_a_run.add_argument("--source-catalog", type=Path, required=True)
    phase_a_run.add_argument("--output-root", type=Path, required=True)
    phase_a_run.add_argument("--manifest-root", type=Path, required=True)
    phase_a_run.add_argument("--snapshot-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_catalog_config()
        if args.command == "rqdata" and args.rqdata_command == "probe":
            return _probe(config)
        if args.command == "catalog" and args.catalog_command == "build":
            return _build(config)
        if args.command == "phase-a" and args.phase_a_command == "run":
            return _run_phase_a(args)
        snapshot = args.snapshot or _latest_snapshot(config)
        if args.catalog_command == "validate":
            _print_json(validate_snapshot(snapshot))
            return 0
        if args.catalog_command == "summarize":
            summary = json.loads((snapshot / "classification_summary.json").read_text(encoding="utf-8"))
            _print_json(summary)
            return 0
    except Exception as exc:
        _print_json({"status": "failed", "error_type": type(exc).__name__}, stream=sys.stderr)
        return 1
    return 2


def _probe(config: CatalogConfig) -> int:
    adapter = create_adapter_from_environment(market=config.market)
    records = normalize_records(adapter.enumerate_fields(config.categories))
    manifest = adapter.capabilities(field_count=len(records))
    config.manifest_root.mkdir(parents=True, exist_ok=True)
    _atomic_json(config.manifest_root / "capability_manifest.json", manifest)
    _print_json(manifest)
    return 0


def _build(config: CatalogConfig) -> int:
    adapter = create_adapter_from_environment(market=config.market)
    result = build_catalog_snapshot(
        adapter=adapter,
        config=config,
        expected_count=BASELINE_COUNT,
        expected_hash=BASELINE_HASH,
        expected_category_counts=BASELINE_ROLE_COUNTS,
    )
    _print_json({**result.manifest, "output_dir": str(result.output_dir)})
    return 0 if result.manifest["status"] == "matched" else 3


def _run_phase_a(args) -> int:
    created_at = datetime.now().astimezone()
    snapshot_id = args.snapshot_id or f"phase-a-v11-{created_at.strftime('%Y%m%dT%H%M%S')}"
    source = pd.read_parquet(args.source_catalog)
    assets, manifest = build_phase_a_assets(
        source,
        ingredient_observations=pd.DataFrame(),
        definitions={},
        event_observations=pd.DataFrame(),
        technical_observations=pd.DataFrame(),
        health_config=load_ingredient_health_config(),
        snapshot_id=snapshot_id,
        created_at=created_at,
    )
    output = persist_phase_a_assets(
        assets,
        manifest=manifest,
        output_root=args.output_root.resolve(),
        public_manifest_root=args.manifest_root.resolve(),
    )
    _print_json({**manifest, "output_dir": str(output)})
    return 0 if manifest["status"] == "complete" else 4


def _latest_snapshot(config: CatalogConfig) -> Path:
    snapshots = sorted(path for path in config.output_root.glob("rqdata-*") if path.is_dir())
    if not snapshots:
        raise FileNotFoundError("no catalog snapshots found")
    return snapshots[-1]


def _atomic_json(path: Path, value: dict[str, object]) -> None:
    temp = path.with_name(f".{path.name}.tmp-{uuid.uuid4().hex}")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


def _print_json(value: dict[str, object], *, stream=None) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True), file=stream or sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())
