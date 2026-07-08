from __future__ import annotations

from rq_platform.etl.update_tradability import update_tradability_dataset


def main() -> None:
    update_tradability_dataset(year=2025, adjust_type="pre")


if __name__ == "__main__":
    main()
