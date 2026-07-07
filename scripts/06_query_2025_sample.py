from rq_platform.data.data_loader import ResearchDataLoader


SYMBOLS = [
    "000001.XSHE",
    "600000.XSHG",
    "000858.XSHE",
    "600519.XSHG",
    "300750.XSHE",
]


def main() -> None:
    frame = ResearchDataLoader().load_prices(
        symbols=SYMBOLS,
        start="2025-01-02",
        end="2025-01-10",
        adjust_type="pre",
        fields=["open", "close", "volume"],
    )
    if frame.empty:
        print("未查到本地 Parquet 数据，请先运行 scripts/04_update_2025_daily_prices.py")
        return

    found_symbols = sorted(frame["order_book_id"].unique().tolist())
    missing_symbols = [symbol for symbol in SYMBOLS if symbol not in found_symbols]
    print(f"rows: {len(frame)}")
    print(f"symbols: {len(found_symbols)}")
    print(f"found_symbols: {found_symbols}")
    if missing_symbols:
        print(f"missing_symbols: {missing_symbols}")
    print(f"date_range: {frame['trade_date'].min()} to {frame['trade_date'].max()}")
    print(frame.head(20))


if __name__ == "__main__":
    main()
