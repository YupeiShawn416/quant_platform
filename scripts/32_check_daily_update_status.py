from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from rq_platform.etl.daily_update_core import STATUS_PATH
from rq_platform.etl.daily_update_reconcile import reconcile_daily_update_coverage


def main() -> int:
    parser = argparse.ArgumentParser(description="Check daily update status and report.")
    parser.add_argument("--status-path", default=str(STATUS_PATH))
    parser.add_argument("--report-json", default="reports/generated/daily_update_report.json")
    args = parser.parse_args()

    status_path = Path(args.status_path)
    if status_path.exists():
        frame = pd.read_csv(status_path)
        print(f"status_path={status_path}")
        print(f"rows={len(frame)}")
        if not frame.empty:
            print(f"latest_run_id={frame['run_id'].dropna().astype(str).iloc[-1]}")
            print(f"failed_rows={int((frame['status'].astype(str) == 'failed').sum())}")
            print(f"skipped_rows={int((frame['status'].astype(str) == 'skipped').sum())}")
    else:
        print(f"status_path={status_path}")
        print("rows=0")

    report_path = Path(args.report_json)
    if report_path.exists():
        data = json.loads(report_path.read_text(encoding="utf-8"))
        print(f"report_json={report_path}")
        print(f"report_file_status={data.get('status')}")
        print(f"report_file_quality_issues_count={data.get('quality_issues_count')}")
        print(f"report_file_status_mismatch_datasets={','.join(data.get('status_mismatch_datasets') or [])}")
        print(f"report_file_zero_row_suspect_count={len(data.get('zero_row_suspect_rows') or [])}")
        print(f"report_file_recommend_rsync={data.get('recommend_rsync')}")
    else:
        print(f"report_json={report_path}")
        print("report_file_status=missing")
    reconcile = reconcile_daily_update_coverage(status_path=status_path)
    live_mismatches = reconcile.get("mismatch_datasets") or []
    live_zero_rows = reconcile.get("zero_row_suspect_rows") or []
    effective_status = "failed" if live_mismatches or live_zero_rows else "success"
    print(f"effective_status={effective_status}")
    print(f"effective_mismatch_datasets={','.join(live_mismatches)}")
    print(f"effective_zero_row_suspect_count={len(live_zero_rows)}")
    print(f"effective_recommend_rsync={reconcile.get('recommend_rsync')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
