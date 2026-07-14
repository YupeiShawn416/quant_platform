from __future__ import annotations

import argparse

from rq_platform.factors.factor_weights import FactorWeightGenerator


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate long-only weights from a factor.")
    parser.add_argument("--factor-id", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--top-quantile", type=float, default=0.2)
    parser.add_argument("--max-names", type=int, default=50)
    parser.add_argument("--rebalance-frequency", default="daily")
    parser.add_argument("--weight-method", default="equal")
    parser.add_argument("--min-coverage-threshold", type=float, default=0.5)
    parser.add_argument("--use-latest-usable-date", action="store_true")
    args = parser.parse_args()
    try:
        result = FactorWeightGenerator().generate(
            factor_id=args.factor_id,
            start_date=args.start_date,
            end_date=args.end_date,
            top_quantile=args.top_quantile,
            max_names=args.max_names,
            rebalance_frequency=args.rebalance_frequency,
            weight_method=args.weight_method,
            min_coverage_threshold=args.min_coverage_threshold,
            use_latest_usable_date=args.use_latest_usable_date,
        )
    except ValueError as exc:
        print(f"error={exc}")
        return 2
    print(f"factor_id={result['factor_id']}")
    print(f"rows={result['row_count']}")
    print(f"target_weights={result['target_weights']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
