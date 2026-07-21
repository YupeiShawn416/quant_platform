from __future__ import annotations

import argparse

from rq_platform.etl.hxz_p3_validation import run_hxz_integrated_validation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run HXZ P3 integrated validation and experimental benchmark integration.")
    parser.add_argument("--data-root", default=None)
    args = parser.parse_args()
    report = run_hxz_integrated_validation(data_root=args.data_root)
    print(f"status={report['status']}")
    print(f"experimental_benchmark={report['integration']['registered_as_experimental_benchmark']}")
    print(f"hxz_better_than_ff3={report['integration']['hxz_better_than_ff3_primary']}")
    print(f"no_lookahead_violations={report['recompute']['no_lookahead_violations']}")
    print("markdown=reports/03_hxz_integrated_validation/hxz_integrated_validation_report.md")
    return 0 if report["status"] == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
