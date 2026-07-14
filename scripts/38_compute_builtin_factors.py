from __future__ import annotations

import argparse

from rq_platform.factors.factor_calculator import FactorCalculator
from rq_platform.factors.factor_definitions import BUILTIN_FACTORS


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute built-in factors.")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--factor-ids", default=",".join(BUILTIN_FACTORS))
    parser.add_argument("--universe", default="all")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    factor_ids = [item.strip() for item in args.factor_ids.split(",") if item.strip()]
    result = FactorCalculator().compute(
        factor_ids=factor_ids,
        start_date=args.start_date,
        end_date=args.end_date,
        universe=args.universe,
        overwrite=args.overwrite,
    )
    for factor_id, row in result.items():
        print(f"{factor_id}: rows={row['rows']} files={len(row['paths'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
