from __future__ import annotations

import argparse

from rq_platform.etl.daily_update_core import run_daily_update
from rq_platform.etl.daily_update_plan import render_daily_update_plan


def main() -> int:
    parser = argparse.ArgumentParser(description="Run daily incremental data lake update.")
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--start-date", default=None)
    parser.add_argument(
        "--datasets",
        default="calendar,instruments,index_prices,prices,tradability,valuation,industry,index_members",
    )
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-daily-update", action="store_true")
    parser.add_argument("--batch-size", type=int, default=300)
    args = parser.parse_args()

    result = run_daily_update(
        start_date=args.start_date,
        end_date=args.end_date,
        datasets=args.datasets,
        force=args.force,
        dry_run=args.dry_run,
        confirm_daily_update=args.confirm_daily_update,
        batch_size=args.batch_size,
    )
    plan = result["plan"]
    print(render_daily_update_plan(plan))
    if args.dry_run:
        return 0

    for item in result["results"]:
        print(item.to_dict())
    report = result["report"]
    print(f"daily_update_report_md={report.get('markdown_path')}")
    print(f"daily_update_report_json={report.get('json_path')}")
    print(f"quality_issues={len(result['quality_issues'])}")
    return 1 if report.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
