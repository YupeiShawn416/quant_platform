from __future__ import annotations

from rq_platform.etl.financial_pit_field_pack_quality import (
    load_financial_pit_field_pack,
    reconcile_with_financial_pit_quarterly,
    summarize_financial_pit_field_pack,
)
from rq_platform.etl.financial_pit_field_pack_report import (
    write_financial_pit_field_pack_coverage_report,
    write_financial_pit_field_pack_reconcile_report,
)


def main() -> int:
    frame = load_financial_pit_field_pack()
    summary = summarize_financial_pit_field_pack(frame)
    coverage_paths = write_financial_pit_field_pack_coverage_report(frame)
    reconcile_paths = write_financial_pit_field_pack_reconcile_report(frame)
    reconcile = reconcile_with_financial_pit_quarterly(frame)
    print("status=success")
    print(f"row_count={summary['row_count']}")
    print(f"symbol_count={summary['symbol_count']}")
    print(f"report_period_count={summary['report_period_count']}")
    print(f"date_range={summary['date_range']}")
    print(f"overlap_fields={','.join(reconcile.get('overlap_fields', []))}")
    print(f"newly_available_fields={','.join(reconcile.get('newly_available_fields', []))}")
    print(f"coverage_markdown={coverage_paths['coverage_md']}")
    print(f"reconcile_markdown={reconcile_paths['reconcile_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
