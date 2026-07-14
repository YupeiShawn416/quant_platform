from __future__ import annotations

import argparse

from rq_platform.factors.factor_analyzer import FactorAnalyzer


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze one factor.")
    parser.add_argument("--factor-id", required=True)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--groups", type=int, default=5)
    args = parser.parse_args()
    summary = FactorAnalyzer().analyze(
        factor_id=args.factor_id,
        start_date=args.start_date,
        end_date=args.end_date,
        groups=args.groups,
    )
    print(f"factor_id={summary['factor_id']}")
    print(f"latest_date={summary['latest_date']}")
    print(f"rows={summary['row_count']}")
    print(f"ic_mean={summary['ic_summary'].get('ic_mean')}")
    print(f"icir={summary['ic_summary'].get('icir')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
