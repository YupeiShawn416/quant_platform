from __future__ import annotations

import argparse
import os
from pathlib import Path

from rq_platform.research.rqdata_field_probe import (
    ProbeConfig,
    run_p0_rqdata_probe,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Small-sample RQData probe for P0 missing raw research fields.")
    parser.add_argument("--stage33-raw-csv", default="reports/generated/research_report_raw_data_availability.csv")
    parser.add_argument("--stage33-derived-csv", default="reports/generated/research_report_derived_field_dependency.csv")
    parser.add_argument("--output-dir", default="reports/generated")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    enable = os.environ.get("ENABLE_RQDATA_PROBE") == "1"
    raw_csv = Path(args.stage33_raw_csv)
    derived_csv = Path(args.stage33_derived_csv)
    if not raw_csv.exists() or not derived_csv.exists():
        print("status=blocked")
        print("reason=Stage 33 outputs are missing. Run: make probe-research-report-data-availability")
        return 2
    if not enable:
        print("status=blocked")
        print("reason=ENABLE_RQDATA_PROBE=1 is required for P0 RQData probe.")
        print("local_only_command=make probe-research-report-data-availability")
        print("rqdata_command=make probe-p0-rqdata-availability ENABLE_RQDATA_PROBE=1")
        return 2

    result = run_p0_rqdata_probe(
        ProbeConfig(
            stage33_raw_csv=raw_csv,
            stage33_derived_csv=derived_csv,
            output_dir=Path(args.output_dir),
            enable_rqdata_probe=enable,
        )
    )
    counts: dict[str, int] = {}
    for row in result["probe_rows"]:
        counts[row["rqdata_probe_status"]] = counts.get(row["rqdata_probe_status"], 0) + 1
    print("status=success")
    print(f"p0_field_count={result['p0_field_count']}")
    print(f"probe_rows={len(result['probe_rows'])}")
    for status, count in sorted(counts.items()):
        print(f"{status}={count}")
    print(f"probe_markdown={Path(args.output_dir) / 'research_report_p0_rqdata_probe.md'}")
    print(f"probe_csv={Path(args.output_dir) / 'research_report_p0_rqdata_probe.csv'}")
    print(f"probe_json={Path(args.output_dir) / 'research_report_p0_rqdata_probe.json'}")
    print(f"after_probe_plan={Path(args.output_dir) / 'research_report_data_backfill_plan_after_probe.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
