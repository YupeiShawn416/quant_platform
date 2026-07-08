# Backtest Result Format

## 结果包结构

每个回测 run 默认写入 `runs/backtests/<run_id>/`：

```text
manifest.json
config.json
summary.json
summary.csv
nav.csv
daily_account.csv
positions.csv
trades.csv
orders.csv
logs.txt
monthly_returns.csv
rolling_metrics.csv
charts.json
error.json
```

`error.json` 只在失败 run 中需要。zip 下载包命名为：

```text
backtest_result_<run_id>.zip
```

## 文件含义

`manifest.json` 描述 run 和包含的结果文件。`config.json` 保存回测配置。
`summary.json` 和 `summary.csv` 保存摘要指标。`nav.csv` 保存策略、基准和超额净值。
`daily_account.csv` 保存每日账户状态。`positions.csv` 保存持仓快照。
`trades.csv` 保存成交明细。`orders.csv` 保存订单明细。`logs.txt` 保存运行日志。
`monthly_returns.csv` 和 `rolling_metrics.csv` 保存扩展分析数据。
`charts.json` 为后续页面图表预留结构化数据。

## CSV 关键字段

`nav.csv`:

```text
trade_date, strategy_nav, benchmark_nav, excess_nav, daily_return,
benchmark_return, excess_return, drawdown
```

`daily_account.csv`:

```text
trade_date, total_value, cash, market_value, position_ratio, daily_pnl, daily_return
```

`positions.csv`:

```text
trade_date, order_book_id, symbol, quantity, close, market_value, weight, pnl
```

`trades.csv`:

```text
trade_date, datetime, order_book_id, symbol, side, quantity, price, amount,
commission, tax, slippage, realized_pnl
```

`orders.csv`:

```text
trade_date, datetime, order_book_id, side, order_type, quantity, price, status, message
```

## 下载 zip

启动 API 后可下载：

```bash
curl "http://127.0.0.1:8000/backtests/demo_run/download" -o /tmp/backtest_result_demo_run.zip
```

如果部署环境设置了强 token，需要加：

```bash
curl -H "X-API-Token: your_token" "http://127.0.0.1:8000/backtests/demo_run/download" -o /tmp/backtest_result_demo_run.zip
```

## 本地复现

```bash
make demo-backtest
make view-demo-backtest
```

多个 zip 后续可以按 `summary.csv`、`nav.csv` 和 `trades.csv` 横向比较。
