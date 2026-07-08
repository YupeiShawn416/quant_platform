from __future__ import annotations

from rq_platform.etl.index_quality_check import (
    check_index_price_dataset,
    print_index_price_check,
)


def main() -> None:
    print_index_price_check(check_index_price_dataset(year=2025))


if __name__ == "__main__":
    main()
