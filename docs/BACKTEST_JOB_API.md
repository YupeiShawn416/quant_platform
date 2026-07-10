# Backtest Job API

V0 支持通过 API 提交策略代码和回测配置，运行 `DailyBacktestEngine`，并把最新结果
设为 `current backtest`。Stage 24 起，每次提交也会写入 run registry，并缓存为独立
`run_id` 结果。

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
  "summary": {},
  "result_urls": {
    "dashboard": "/ui/backtests/runs/api_demo_backtest",
    "download": "/backtests/runs/api_demo_backtest/download"
  }
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

`current` 继续代表最近一次结果：

```text
POST /backtests/run -> 清理旧 current -> 运行新 job -> 复制结果到 current
```

同时，每次回测会写入独立 run：

```text
GET /backtests/runs
GET /backtests/runs/{run_id}
GET /backtests/runs/{run_id}/download
```

长期保存结果仍需要下载 zip：

```text
GET /backtests/current/download
GET /backtests/runs/{run_id}/download
```

`DELETE /backtests/current` 会删除当前临时结果。

## 安全边界

local execution mode 仅用于本地开发和测试。生产环境必须设置：

```env
BACKTEST_EXECUTION_MODE=docker
```

上传策略最大 200KB，平台固定写入 `strategy.py`，不接受用户路径，也不会挂载 `.env`。

## POST /backtests/run-package

上传 Strategy Package：

```bash
curl -F "file=@/tmp/demo_weights_strategy_package.zip" \
  http://127.0.0.1:8000/backtests/run-package
```

V1 主路径是 `weights` 模式。上传成功后可以继续通过 `/backtests/current/*` 查看最新结果，
也可以通过 `/backtests/runs/{run_id}/*` 查看自己的独立结果。
