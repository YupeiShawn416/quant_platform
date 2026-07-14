from __future__ import annotations

import argparse

from rq_platform.etl.daily_update_reconcile import reconcile_daily_update_coverage, write_reconcile_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile daily update status with actual parquet coverage.")
    parser.add_argument("--expected-end-date", default=None)
    args = parser.parse_args()

    report = reconcile_daily_update_coverage(expected_end_date=args.expected_end_date)
    markdown_path, json_path = write_reconcile_report(report)
    print(f"markdown={markdown_path}")
    print(f"json={json_path}")
    print(f"mismatch_datasets={','.join(report.get('mismatch_datasets') or [])}")
    print(f"zero_row_suspect_count={len(report.get('zero_row_suspect_rows') or [])}")
    print(f"recommend_rsync={report.get('recommend_rsync')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
