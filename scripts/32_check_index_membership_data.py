from __future__ import annotations

from rq_platform.etl.index_membership_quality_check import (
    check_index_membership_dataset,
    print_index_membership_check,
)


def main() -> None:
    print_index_membership_check(check_index_membership_dataset(year=2025))


if __name__ == "__main__":
    main()
