from __future__ import annotations

import argparse

from rq_platform.etl.hxz_p2_factors import build_hxz_factors


def main() -> int:
    parser = argparse.ArgumentParser(description="Build HXZ P2 2x3x3 portfolios and four monthly factors.")
    parser.add_argument("--panel-path", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--start-month", default="2016-07")
    args = parser.parse_args()

    report = build_hxz_factors(panel_path=args.panel_path, output_dir=args.output_dir, start_month=args.start_month)
    print(f"status={report['status']}")
    print(f"start_month={report['factor_range']['start_month']}")
    print(f"end_month={report['factor_range']['end_month']}")
    print(f"months={report['factor_range']['months']}")
    print(f"assignments={report['rows']['assignments']}")
    print(f"portfolio_returns={report['rows']['portfolio_returns']}")
    print(f"no_lookahead_violations={report['quality']['no_lookahead_violations']}")
    print("markdown=reports/02_hxz_factor_construction/hxz_p2_factor_construction.md")
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
