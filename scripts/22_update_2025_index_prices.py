from __future__ import annotations

from rq_platform.etl.update_index_prices import update_index_prices


def main() -> None:
    update_index_prices(year=2025)


if __name__ == "__main__":
    main()
