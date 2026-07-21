from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from rq_platform.etl.financial_pit_field_pack_core import run_financial_pit_field_pack_backfill
from rq_platform.etl.financial_pit_field_pack_plan import (
    DEFAULT_PROBE_CSV,
    build_financial_pit_field_pack_task,
    load_available_financial_pit_fields,
    parse_symbols,
)
from rq_platform.etl.financial_pit_field_pack_quality import load_financial_pit_field_pack, summarize_financial_pit_field_pack
from rq_platform.etl.financial_pit_field_pack_report import (
    write_financial_pit_field_pack_coverage_report,
    write_financial_pit_field_pack_quality_report,
    write_financial_pit_field_pack_reconcile_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill Stage 33B verified financial PIT field pack.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--fields", default=None)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--probe-csv", default=str(DEFAULT_PROBE_CSV))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--confirm-financial-pit-field-pack-backfill", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_fields = [item.strip() for item in args.fields.split(",") if item.strip()] if args.fields else None
    available_fields = load_available_financial_pit_fields(args.probe_csv, requested_fields)
    symbols = parse_symbols(args.symbols) if args.symbols else None
    task = build_financial_pit_field_pack_task(
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=symbols,
        fields=available_fields,
        batch_size=args.batch_size,
        dry_run=args.dry_run or not args.confirm_financial_pit_field_pack_backfill,
        overwrite=args.overwrite,
    )
    result = run_financial_pit_field_pack_backfill(task, confirm=args.confirm_financial_pit_field_pack_backfill)
    print(f"status={result['status']}")
    print(f"symbols={result['symbol_count']}")
    print(f"fields={','.join(field['canonical_field'] for field in result['fields'])}")
    print(f"expected_api_calls={result['expected_api_calls']}")
    if result["status"] == "dry_run":
        print(json.dumps({k: result[k] for k in ["start_date", "end_date", "start_quarter", "end_quarter"]}, ensure_ascii=False))
        return 0

    frame = load_financial_pit_field_pack()
    quality_paths = write_financial_pit_field_pack_quality_report(frame)
    coverage_paths = write_financial_pit_field_pack_coverage_report(frame)
    reconcile_paths = write_financial_pit_field_pack_reconcile_report(frame)
    summary = summarize_financial_pit_field_pack(frame)
    print(f"row_count={summary['row_count']}")
    print(f"quality_report={quality_paths['quality_md']}")
    print(f"coverage_report={coverage_paths['coverage_md']}")
    print(f"reconcile_report={reconcile_paths['reconcile_md']}")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
