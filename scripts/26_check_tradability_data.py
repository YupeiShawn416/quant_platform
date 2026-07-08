from __future__ import annotations

from rq_platform.etl.tradability_quality_check import (
    check_tradability_dataset,
    print_tradability_check,
)


def main() -> None:
    print_tradability_check(check_tradability_dataset(year=2025))


if __name__ == "__main__":
    main()
