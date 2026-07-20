from __future__ import annotations

import argparse
import json

from rq_platform.etl.hxz_p0_backfill import (
    build_hxz_p0_plan,
    record_hxz_smoke_in_plan,
    run_hxz_p0_smoke,
    update_hxz_backfill_plan_file,
    write_hxz_p0_dry_run_report,
    write_planned_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="HXZ P0 backfill dry-run and smoke workflow.")
    parser.add_argument("--dataset", default="all")
    parser.add_argument("--start-date", default="2016-01-04")
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--start-quarter", default="2015q4")
    parser.add_argument("--end-quarter", default=None)
    parser.add_argument("--symbol-batch-size", type=int, default=200)
    parser.add_argument("--date-chunk-size", type=int, default=252)
    parser.add_argument("--quarter-chunk-size", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output-dir", default="reports/data_audit")
    args = parser.parse_args()

    if not args.dry_run and not args.smoke:
        raise SystemExit("Refusing to run: pass --dry-run or --smoke explicitly.")
    if args.dry_run:
        plan = build_hxz_p0_plan(
            datasets=args.dataset,
            start_date=args.start_date,
            end_date=args.end_date,
            start_quarter=args.start_quarter,
            end_quarter=args.end_quarter,
            symbol_batch_size=args.symbol_batch_size,
            date_chunk_size=args.date_chunk_size,
            quarter_chunk_size=args.quarter_chunk_size,
        )
        outputs = write_hxz_p0_dry_run_report(plan, output_dir=args.output_dir)
        status_path = write_planned_status(plan)
        plan_path = update_hxz_backfill_plan_file(plan)
        print(f"status=dry_run_ready")
        print(f"datasets={plan['summary']['dataset_count']}")
        print(f"estimated_api_calls={plan['summary']['total_estimated_api_calls']}")
        print(f"estimated_rows={plan['summary']['total_estimated_rows']}")
        print(f"dry_run_markdown={outputs['markdown']}")
        print(f"dry_run_json={outputs['json']}")
        print(f"status_log={status_path}")
        print(f"backfill_plan={plan_path}")
    if args.smoke:
        result = run_hxz_p0_smoke(output_dir=args.output_dir)
        plan_path = record_hxz_smoke_in_plan(result)
        print(f"status={result['status']}")
        print(f"rqdata_calls={result.get('rqdata_calls', 0)}")
        print(f"smoke_markdown={args.output_dir}/hxz_p0_smoke_validation.md")
        print(f"smoke_json={args.output_dir}/hxz_p0_smoke_validation.json")
        print(f"backfill_plan={plan_path}")
        if result["status"] != "success":
            print(json.dumps({"reason": result.get("reason")}, ensure_ascii=False))
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
