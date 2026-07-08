from __future__ import annotations

import argparse

from rq_platform.etl.update_industry import update_industry_classification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update 2025 A-share industry classification.")
    parser.add_argument("--max-dates", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    update_industry_classification(year=2025, max_dates=args.max_dates)


if __name__ == "__main__":
    main()
