from __future__ import annotations

import argparse

from rq_platform.etl.intraday_snapshot_quality import check_intraday_snapshot_quality
from rq_platform.etl.intraday_snapshot_report import write_intraday_snapshot_quality_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Check intraday snapshot quality.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--min-symbols-per-snapshot", type=int, default=100)
    args = parser.parse_args()

    issues = check_intraday_snapshot_quality(
        data_root=args.data_root,
        min_symbols_per_snapshot=args.min_symbols_per_snapshot,
    )
    report = write_intraday_snapshot_quality_report(quality_issues=issues, data_root=args.data_root)
    print(f"quality_issues={len(issues)}")
    print(f"quality_errors={sum(1 for issue in issues if issue.severity == 'error')}")
    print(f"quality_warnings={sum(1 for issue in issues if issue.severity == 'warning')}")
    print(f"report={report}")
    for issue in issues[:50]:
        print(issue.to_dict())
    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
