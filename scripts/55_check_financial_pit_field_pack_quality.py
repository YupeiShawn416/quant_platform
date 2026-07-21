from __future__ import annotations

from rq_platform.etl.financial_pit_field_pack_quality import (
    check_financial_pit_field_pack,
    load_financial_pit_field_pack,
)
from rq_platform.etl.financial_pit_field_pack_report import write_financial_pit_field_pack_quality_report


def main() -> int:
    frame = load_financial_pit_field_pack()
    issues = check_financial_pit_field_pack(frame)
    paths = write_financial_pit_field_pack_quality_report(frame)
    errors = [issue for issue in issues if issue.severity == "error"]
    warnings = [issue for issue in issues if issue.severity == "warning"]
    print(f"status={'success' if not errors else 'failed'}")
    print(f"row_count={len(frame)}")
    print(f"quality_issues={len(issues)}")
    print(f"errors={len(errors)}")
    print(f"warnings={len(warnings)}")
    print(f"markdown={paths['quality_md']}")
    print(f"json={paths['quality_json']}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
