from __future__ import annotations

import argparse
import json

from rq_platform.etl.financial_cashflow_field_pack_plan import (
    DATASET_NAME,
    OUTPUT_FILENAME,
    STATUS_PATH,
    build_financial_cashflow_field_pack_task,
    parse_symbols,
    select_cashflow_fields,
)
from rq_platform.etl.financial_pit_field_pack_core import run_financial_pit_field_pack_backfill
from rq_platform.etl.financial_pit_field_pack_quality import load_financial_pit_field_pack, summarize_financial_pit_field_pack
from rq_platform.etl.financial_pit_field_pack_report import (
    write_financial_pit_field_pack_coverage_report,
    write_financial_pit_field_pack_quality_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill RQData financial cash-flow PIT field pack.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--symbols", default=None)
    parser.add_argument("--fields", default=None)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--confirm-financial-cashflow-field-pack-backfill", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    requested_fields = [item.strip() for item in args.fields.split(",") if item.strip()] if args.fields else None
    fields = select_cashflow_fields(requested_fields)
    symbols = parse_symbols(args.symbols) if args.symbols else None
    task = build_financial_cashflow_field_pack_task(
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=symbols,
        fields=fields,
        batch_size=args.batch_size,
        dry_run=args.dry_run or not args.confirm_financial_cashflow_field_pack_backfill,
        overwrite=args.overwrite,
    )
    result = run_financial_pit_field_pack_backfill(
        task,
        confirm=args.confirm_financial_cashflow_field_pack_backfill,
        dataset_name=DATASET_NAME,
        output_filename=OUTPUT_FILENAME,
        status_path=STATUS_PATH,
    )
    print(f"status={result['status']}")
    print(f"symbols={result['symbol_count']}")
    print(f"fields={','.join(field['canonical_field'] for field in result['fields'])}")
    print(f"expected_api_calls={result['expected_api_calls']}")
    if result["status"] == "dry_run":
        print(json.dumps({k: result[k] for k in ["start_date", "end_date", "start_quarter", "end_quarter"]}, ensure_ascii=False))
        return 0

    frame = load_financial_pit_field_pack(dataset_name=DATASET_NAME)
    quality_paths = write_financial_pit_field_pack_quality_report(
        frame,
        dataset_name=DATASET_NAME,
        title="Financial Cashflow Field Pack",
    )
    coverage_paths = write_financial_pit_field_pack_coverage_report(
        frame,
        dataset_name=DATASET_NAME,
        title="Financial Cashflow Field Pack",
    )
    summary = summarize_financial_pit_field_pack(frame)
    print(f"row_count={summary['row_count']}")
    print(f"quality_report={quality_paths['quality_md']}")
    print(f"coverage_report={coverage_paths['coverage_md']}")
    return 0 if result["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
