from __future__ import annotations

import argparse

from rq_platform.etl.intraday_snapshot_report import write_intraday_snapshot_coverage_report
from rq_platform.etl.intraday_snapshot_quality import summarize_intraday_snapshot_coverage


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit intraday snapshot coverage.")
    parser.add_argument("--data-root", default=None)
    args = parser.parse_args()

    coverage = summarize_intraday_snapshot_coverage(args.data_root)
    report = write_intraday_snapshot_coverage_report(data_root=args.data_root)
    print(f"coverage_rows={len(coverage)}")
    print(f"report={report}")
    if not coverage.empty:
        print(coverage.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
