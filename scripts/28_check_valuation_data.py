from __future__ import annotations

from rq_platform.etl.valuation_quality_check import (
    check_valuation_dataset,
    print_valuation_check,
)


def main() -> None:
    print_valuation_check(check_valuation_dataset(year=2025))


if __name__ == "__main__":
    main()
