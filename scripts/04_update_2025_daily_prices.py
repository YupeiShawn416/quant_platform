from __future__ import annotations

import argparse

from rq_platform.etl.update_all_daily_prices import update_all_daily_prices


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update 2025 A-share daily prices.")
    parser.add_argument("--full", action="store_true", help="Run all batches for 2025.")
    parser.add_argument("--batch-size", type=int, default=300)
    parser.add_argument("--max-batches", type=int, default=1)
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    max_batches = None if args.full else args.max_batches
    update_all_daily_prices(
        start="2025-01-01",
        end="2025-12-31",
        year=2025,
        adjust_types=["pre", "none"],
        batch_size=args.batch_size,
        resume=not args.no_resume,
        max_batches=max_batches,
    )
    if not args.full:
        print("smoke test 成功；已经抓取第 1 个 batch。")
        print("如需完整抓取 2025 全 A，可运行：")
        print("PYTHONPATH=src python scripts/04_update_2025_daily_prices.py --full")


if __name__ == "__main__":
    main()
