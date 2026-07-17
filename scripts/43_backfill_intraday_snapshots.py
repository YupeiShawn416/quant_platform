from __future__ import annotations

import argparse

from rq_platform.etl.intraday_snapshot_core import run_intraday_snapshot_backfill
from rq_platform.etl.intraday_snapshot_plan import render_intraday_snapshot_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill A-share intraday snapshot points.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--snapshot-times", default="09:45,09:55,10:00,14:30,14:45,14:55")
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--confirm-intraday-snapshot-backfill", action="store_true")
    args = parser.parse_args()

    dry_run = args.dry_run or not args.confirm_intraday_snapshot_backfill
    result = run_intraday_snapshot_backfill(
        start_date=args.start_date,
        end_date=args.end_date,
        snapshot_times=args.snapshot_times,
        batch_size=args.batch_size,
        dry_run=dry_run,
        overwrite=args.overwrite,
        confirm_intraday_snapshot_backfill=args.confirm_intraday_snapshot_backfill,
    )
    print(render_intraday_snapshot_plan(result["plan"]))
    if dry_run:
        print("dry_run=True; no RQData call was made")
        return 0
    for item in result["results"]:
        print(item.to_dict())
    print(f"quality_issues={len(result['quality_issues'])}")
    print(f"report={result['report']}")
    return 1 if result["report"].get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
