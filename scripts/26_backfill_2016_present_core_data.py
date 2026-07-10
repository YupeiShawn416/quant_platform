from __future__ import annotations

import argparse

from rq_platform.etl.backfill_core import render_plan, run_core_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill 2016-present core data lake datasets.")
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", required=True)
    parser.add_argument(
        "--datasets",
        default="prices,index_prices,calendar,instruments,tradability,valuation,industry,index_members",
    )
    parser.add_argument("--years", default=None, help="Comma separated years, e.g. 2016,2017")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--max-securities", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--confirm-full-backfill", action="store_true")
    args = parser.parse_args()

    years = [int(item) for item in args.years.split(",") if item.strip()] if args.years else None
    datasets = [item.strip() for item in args.datasets.split(",") if item.strip()]
    result = run_core_backfill(
        start_date=args.start_date,
        end_date=args.end_date,
        datasets=datasets,
        years=years,
        force=args.force,
        dry_run=args.dry_run,
        smoke=args.smoke,
        confirm_full_backfill=args.confirm_full_backfill,
        max_securities=args.max_securities,
        batch_size=args.batch_size,
    )
    if args.dry_run:
        print(render_plan(result))
    else:
        for item in result:
            print(item.to_dict())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
