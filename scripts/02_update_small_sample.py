from rq_platform.etl.update_calendar import update_calendar
from rq_platform.etl.update_daily_prices import update_daily_prices
from rq_platform.etl.update_instruments import update_instruments


SYMBOLS = ["000001.XSHE", "600000.XSHG"]
START = "2025-01-02"
END = "2025-01-10"
ADJUST_TYPES = ["pre", "none"]


def main() -> None:
    print("=== update small rqdata sample ===")
    update_calendar(start="2025-01-01", end="2025-12-31")
    update_instruments()
    update_daily_prices(SYMBOLS, START, END, ADJUST_TYPES)
    print("small sample update finished")


if __name__ == "__main__":
    main()
