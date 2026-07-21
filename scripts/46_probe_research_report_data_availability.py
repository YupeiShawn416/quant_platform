from __future__ import annotations

import argparse

from rq_platform.research.data_availability_probe import (
    build_research_report_data_availability,
    is_rqdata_probe_enabled,
)
from rq_platform.research.data_availability_report import (
    build_backfill_plan,
    write_research_report_availability_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe research-report raw data availability.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output-dir", default="reports/generated")
    parser.add_argument(
        "--enable-rqdata-probe",
        action="store_true",
        help="Run limited RQData schema probes. Default is local-only.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    enable_rqdata_probe = args.enable_rqdata_probe or is_rqdata_probe_enabled()
    result = build_research_report_data_availability(
        data_root=args.data_root,
        enable_rqdata_probe=enable_rqdata_probe,
    )
    paths = write_research_report_availability_outputs(result, output_dir=args.output_dir)
    plan = build_backfill_plan(result["raw_availability"], result["derived_dependency"])

    raw_count = len(result["raw_availability"])
    derived_count = len(result["derived_dependency"])
    missing_count = sum(1 for row in result["raw_availability"] if row["local_status"] == "missing")
    blocked_count = sum(
        1
        for row in result["derived_dependency"]
        if row["current_raw_field_status"].startswith("blocked")
    )
    print("status=success")
    print(f"rqdata_probe_enabled={enable_rqdata_probe}")
    print(f"raw_fields={raw_count}")
    print(f"derived_fields={derived_count}")
    print(f"missing_raw_fields={missing_count}")
    print(f"blocked_derived_fields={blocked_count}")
    print(f"data_packs={len(plan)}")
    for name, path in paths.items():
        print(f"{name}={path}")


if __name__ == "__main__":
    main()
