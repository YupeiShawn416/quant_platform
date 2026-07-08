# Backtest Engine V0

`DailyBacktestEngine` 是本项目自研日频多头回测引擎的第一版。它用于把本地
Parquet 行情、策略权重和标准 Backtest Result Bundle 串成闭环。

## 支持范围

1. 日频股票多头策略。
2. 每日调用 `generate_weights(context, data)`。
3. 使用 `ResearchDataLoader` 只读本地 Parquet 行情。
4. 按目标权重调仓。
5. 生成 `summary/nav/daily_account/positions/trades/orders/logs/charts` 等标准结果。
6. 失败由 Worker 写 `error.json` 和 `logs.txt`。

## 撮合规则

```text
买入成交价 = close * (1 + slippage_rate)
卖出成交价 = close * (1 - slippage_rate)
买入费用 = commission
卖出费用 = commission + tax
数量约束 = lot_size，默认 100 股
现金不足 = 自动缩小买入数量
```

## 不支持

```text
盘中交易
做空
融资融券
期货/期权
复杂撮合队列
真实 RQAlpha engine
真实任务队列
```

## 运行 demo

```bash
make demo-daily-backtest
make view-demo-daily-backtest
make backtest-api-smoke
```

demo 策略位于：

```text
strategies/demo_small_cap/
```

结果写入：

```text
runs/backtests/demo_daily_backtest/
```

## 与 RQAlpha 的关系

V0 先保持自研、可解释、可测试。后续可以把同一套标准结果包与 RQAlpha runner
对接，但本阶段不调用 RQData、不更新 bundle、不接真实 RQAlpha。

## Job API

现在可以通过 `POST /backtests/run` 提交策略代码和配置。平台会清理旧 current，
运行 V0 日频回测，并把最新标准结果包复制到 `runs/backtests/current/`。

`POST /backtests/run-package` 支持上传 Strategy Package。weights 模式会读取
`weights.parquet` 或 `weights.csv`，转换为目标权重调仓策略，再进入同一套
`DailyBacktestEngine` 撮合和绩效链路。
