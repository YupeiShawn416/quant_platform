from __future__ import annotations

import argparse

from rq_platform.etl.update_valuation import update_valuation_dataset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update 2025 A-share valuation factors.")
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--max-batches", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    update_valuation_dataset(
        year=2025,
        batch_size=args.batch_size,
        max_batches=args.max_batches,
    )


if __name__ == "__main__":
    main()
