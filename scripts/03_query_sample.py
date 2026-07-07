from rq_platform.data.data_loader import ResearchDataLoader


def main() -> None:
    loader = ResearchDataLoader()
    frame = loader.load_prices(
        symbols=["000001.XSHE", "600000.XSHG"],
        start="2025-01-02",
        end="2025-01-10",
        adjust_type="pre",
        fields=["open", "close", "volume"],
    )
    if frame.empty:
        print("未查到本地 Parquet 数据，请先运行 scripts/02_update_small_sample.py")
        return
    print(frame)


if __name__ == "__main__":
    main()
