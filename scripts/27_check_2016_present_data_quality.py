from __future__ import annotations

import argparse

from rq_platform.etl.data_quality_checks import run_data_quality_checks, write_quality_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 2016-present data quality checks.")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--output-dir", default="reports/generated")
    args = parser.parse_args()

    issues = run_data_quality_checks(args.data_root)
    md_path, json_path = write_quality_report(issues, args.output_dir)
    print(f"issues={len(issues)}")
    print(f"markdown={md_path}")
    print(f"json={json_path}")
    return 1 if any(issue.severity == "error" for issue in issues) else 0


if __name__ == "__main__":
    raise SystemExit(main())
