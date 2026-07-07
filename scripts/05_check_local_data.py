from rq_platform.etl.quality_check import check_all_price_datasets, print_price_check


def main() -> None:
    for result in check_all_price_datasets(year=2025):
        print_price_check(result)


if __name__ == "__main__":
    main()
