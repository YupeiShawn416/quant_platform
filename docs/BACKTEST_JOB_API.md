# Backtest Job API

V0 支持通过 API 提交策略代码和回测配置，运行 `DailyBacktestEngine`，并把最新结果
设为 single-user `current backtest`。

## POST /backtests/run

请求体使用 JSON，不使用 multipart：

```json
{
  "strategy_code": "def generate_weights(context, data):\n    return {'000001.XSHE': 0.5}\n",
  "config": {
    "run_id": "api_demo_backtest",
    "strategy_name": "api_demo",
    "start_date": "2025-01-02",
    "end_date": "2025-02-28",
    "initial_cash": 1000000,
    "benchmark": "000300.XSHG",
    "adjust_type": "pre",
    "frequency": "daily",
    "commission_rate": 0.0003,
    "tax_rate": 0.001,
    "slippage_rate": 0.0001,
    "lot_size": 100,
    "price_field": "close"
  }
}
```

成功返回：

```json
{
  "status": "success",
  "job_id": "...",
  "run_id": "api_demo_backtest",
  "summary": {}
}
```

运行失败时返回 `status=failed`，同时 current 中保留 `error.json` 和 `logs.txt`。

## Config 必填字段

```text
run_id
strategy_name
start_date
end_date
initial_cash
adjust_type
frequency
commission_rate
tax_rate
slippage_rate
lot_size
price_field
```

## Current 生命周期

平台 V0 是单用户模型，只保留一个 current backtest：

```text
POST /backtests/run -> 清理旧 current -> 运行新 job -> 复制结果到 current
```

长期保存结果需要下载 zip：

```text
GET /backtests/current/download
```

`DELETE /backtests/current` 会删除当前临时结果。

## 安全边界

local execution mode 仅用于本地开发和测试。生产环境必须设置：

```env
BACKTEST_EXECUTION_MODE=docker
```

上传策略最大 200KB，平台固定写入 `strategy.py`，不接受用户路径，也不会挂载 `.env`。
