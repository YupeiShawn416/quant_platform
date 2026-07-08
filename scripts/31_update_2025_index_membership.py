from __future__ import annotations

import argparse

from rq_platform.etl.update_index_membership import update_index_membership


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update 2025 index components and weights.")
    parser.add_argument("--max-dates", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    update_index_membership(year=2025, max_dates=args.max_dates)


if __name__ == "__main__":
    main()
