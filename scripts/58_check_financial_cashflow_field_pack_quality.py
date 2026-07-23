from rq_platform.etl.financial_cashflow_field_pack_plan import DATASET_NAME
from rq_platform.etl.financial_pit_field_pack_quality import (
    check_financial_pit_field_pack,
    load_financial_pit_field_pack,
)
from rq_platform.etl.financial_pit_field_pack_report import write_financial_pit_field_pack_quality_report


def main() -> int:
    frame = load_financial_pit_field_pack(dataset_name=DATASET_NAME)
    issues = check_financial_pit_field_pack(frame)
    paths = write_financial_pit_field_pack_quality_report(
        frame,
        dataset_name=DATASET_NAME,
        title="Financial Cashflow Field Pack",
    )
    print(f"rows={len(frame)}")
    print(f"issues={len(issues)}")
    print(f"quality_report={paths['quality_md']}")
    return 0 if not any(issue.severity == "error" for issue in issues) else 1


if __name__ == "__main__":
    raise SystemExit(main())
