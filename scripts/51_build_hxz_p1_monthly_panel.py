from __future__ import annotations

import argparse

from rq_platform.etl.hxz_p1_monthly_panel import build_hxz_monthly_research_panel


def main() -> int:
    parser = argparse.ArgumentParser(description="Build HXZ P1 monthly no-lookahead research panel.")
    parser.add_argument("--start-month", default=None, help="Inclusive YYYY-MM month. Defaults to full local calendar.")
    parser.add_argument("--end-month", default=None, help="Inclusive YYYY-MM month. Defaults to full local calendar.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    report = build_hxz_monthly_research_panel(
        data_root=args.data_root,
        start_month=args.start_month,
        end_month=args.end_month,
        output_dir=args.output_dir,
    )
    print(f"status={report['status']}")
    print(f"rows={report['rows']}")
    print(f"symbols={report['symbols']}")
    print(f"months={report['months']}")
    print(f"no_lookahead_violations={report['no_lookahead_violations']}")
    print("markdown=reports/data_audit/hxz_p1_monthly_panel.md")
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
