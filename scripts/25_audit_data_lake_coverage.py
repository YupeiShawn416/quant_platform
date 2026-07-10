from __future__ import annotations

import argparse

from rq_platform.etl.data_lake_audit import audit_data_lake, write_audit_reports


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit local data lake coverage.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--output-dir", default="reports/generated")
    args = parser.parse_args()

    frame = audit_data_lake(
        data_root=args.data_root,
        expected_start_year=args.start_year,
        expected_end_year=args.end_year,
    )
    md_path, csv_path = write_audit_reports(frame, args.output_dir)
    print(f"datasets={frame['dataset'].nunique() if not frame.empty else 0}")
    print(f"rows={len(frame)}")
    print(f"markdown={md_path}")
    print(f"csv={csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
