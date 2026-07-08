from __future__ import annotations

import argparse

from rq_platform.etl.index_quality_check import (
    check_index_price_dataset,
    print_index_price_check,
)
from rq_platform.etl.industry_quality_check import (
    check_industry_dataset,
    print_industry_check,
)
from rq_platform.etl.index_membership_quality_check import (
    check_index_membership_dataset,
    print_index_membership_check,
)
from rq_platform.etl.tradability_quality_check import (
    check_tradability_dataset,
    print_tradability_check,
)
from rq_platform.etl.valuation_quality_check import (
    check_valuation_dataset,
    print_valuation_check,
)
from rq_platform.etl.update_index_prices import update_index_prices
from rq_platform.etl.update_industry import update_industry_classification
from rq_platform.etl.update_index_membership import update_index_membership
from rq_platform.etl.update_tradability import update_tradability_dataset
from rq_platform.etl.update_valuation import update_valuation_dataset
from rq_platform.etl.quality_check import check_all_price_datasets, print_price_check


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local daily data update tasks.")
    parser.add_argument("--date", help="Target update date, reserved for incremental tasks.")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--skip-stocks", action="store_true")
    parser.add_argument("--skip-index", action="store_true")
    parser.add_argument("--skip-tradability", action="store_true")
    parser.add_argument("--skip-valuation", action="store_true")
    parser.add_argument("--skip-industry", action="store_true")
    parser.add_argument("--skip-index-membership", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(f"daily data update: year={args.year} date={args.date or ''} check_only={args.check_only}")

    if not args.skip_index and not args.check_only:
        update_index_prices(year=args.year)
    elif args.skip_index:
        print("skip index update")

    if not args.skip_stocks and not args.check_only:
        print("stock daily update is not wired into this daily entry yet; use scripts/04_update_2025_daily_prices.py")
    elif args.skip_stocks:
        print("skip stock update")

    if not args.skip_tradability and not args.check_only:
        update_tradability_dataset(year=args.year)
    elif args.skip_tradability:
        print("skip tradability update")

    if not args.skip_valuation and not args.check_only:
        update_valuation_dataset(year=args.year)
    elif args.skip_valuation:
        print("skip valuation update")

    if not args.skip_industry and not args.check_only:
        update_industry_classification(year=args.year)
    elif args.skip_industry:
        print("skip industry update")

    if not args.skip_index_membership and not args.check_only:
        update_index_membership(year=args.year)
    elif args.skip_index_membership:
        print("skip index membership update")

    if not args.skip_stocks:
        for result in check_all_price_datasets(year=args.year):
            print_price_check(result)
    print_index_price_check(check_index_price_dataset(year=args.year))
    print_tradability_check(check_tradability_dataset(year=args.year))
    print_valuation_check(check_valuation_dataset(year=args.year))
    print_industry_check(check_industry_dataset(year=args.year))
    print_index_membership_check(check_index_membership_dataset(year=args.year))


if __name__ == "__main__":
    main()
