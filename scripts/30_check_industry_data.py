from __future__ import annotations

from rq_platform.etl.industry_quality_check import check_industry_dataset, print_industry_check


def main() -> None:
    print_industry_check(check_industry_dataset(year=2025))


if __name__ == "__main__":
    main()
