from rq_platform.etl.financial_cashflow_field_pack_plan import DATASET_NAME
from rq_platform.etl.financial_pit_field_pack_quality import (
    load_financial_pit_field_pack,
    summarize_financial_pit_field_pack,
)
from rq_platform.etl.financial_pit_field_pack_report import write_financial_pit_field_pack_coverage_report


def main() -> int:
    frame = load_financial_pit_field_pack(dataset_name=DATASET_NAME)
    summary = summarize_financial_pit_field_pack(frame)
    coverage_paths = write_financial_pit_field_pack_coverage_report(
        frame,
        dataset_name=DATASET_NAME,
        title="Financial Cashflow Field Pack",
    )
    print(f"row_count={summary['row_count']}")
    print(f"symbols={summary['symbol_count']}")
    print(f"report_period_count={summary['report_period_count']}")
    print(f"info_date_range={summary['date_range']}")
    print(f"coverage_report={coverage_paths['coverage_md']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
