# Daily ETL

每日数据更新入口用于把本地数据湖逐步扩展成可重复运行的生产任务。

V0 当前支持：

```bash
make update-index-2025
make check-index-data
make update-tradability-2025
make check-tradability-data
make daily-data-update
```

`make update-index-2025` 通过 RQData 只读抓取常见指数 2025 日频行情，并覆盖写入：

```text
data/research_data/rqdata/index_prices_1d/year=2025.parquet
```

默认指数：

```text
000300.XSHG
000905.XSHG
000852.XSHG
000001.XSHG
399001.XSHE
399006.XSHE
```

`make check-index-data` 检查指数数量、日期范围、每个指数行数、`close` 缺失和
`trade_date + order_book_id` 重复键。

`make update-tradability-2025` 基于本地交易日历、`instruments` 和
`prices_1d_pre/year=2025.parquet` 生成：

```text
data/research_data/rqdata/tradability_1d/year=2025.parquet
```

`make check-tradability-data` 检查可交易性行数、重复键、可买/可卖缺失和不可交易原因。

`make daily-data-update` 目前实际执行指数更新、可交易性生成和质量检查：

```bash
PYTHONPATH=src python scripts/24_daily_data_update.py --year 2025 --skip-stocks
```

参数：

```text
--date YYYY-MM-DD
--year 2025
--skip-stocks
--skip-index
--skip-tradability
--check-only
```

股票日频全量更新仍使用：

```bash
PYTHONPATH=src python scripts/04_update_2025_daily_prices.py --full
```

后续每日任务会继续串联股票增量、指数增量、派生特征和质量报告。所有实际数据文件
位于 ignored 的 `data/` 目录，不进入 Git。
