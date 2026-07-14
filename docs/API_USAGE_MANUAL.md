# Quant Platform API 使用手册及规范

本文面向研究员、策略开发者和内部 Agent。它说明如何安全、稳定地调用 Quant Platform API。

当前服务器示例：

```text
http://39.106.218.30
```

当前数据支持区间：

```text
2016-01-04 to 2026-07-10
```

不要在文档、代码、GitHub、聊天记录或日志里写真实 API token。

## 1. 基本原则

- `/health` 不需要 token。
- 除 `/health` 外，部署环境 API 都需要 token。
- 研究员只通过 API 拉数据、提交回测和查看结果。
- 研究员不需要 RQData、服务器密码、数据库账号或服务器文件权限。
- 不要把平台 API 当成外部数据分发服务。
- 不要暴力循环拉取全市场全历史数据。

## 2. Base URL

本地开发：

```text
http://127.0.0.1:8000
```

服务器：

```text
http://39.106.218.30
```

当前服务器使用 `http`，不是 `https`。

## 3. 鉴权规范

Header：

```text
X-API-Token: <your_token>
```

Mac / Linux：

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="your_token_here"
```

Windows PowerShell：

```powershell
$env:QUANT_PLATFORM_API_URL = "http://39.106.218.30"
$env:QUANT_PLATFORM_API_TOKEN = "your_token_here"
```

规范：

- token 由管理员单独发放。
- 一人一个 token。
- token 泄露后联系管理员禁用并重发。
- 禁止把 token 写入源码、配置文件、README、notebook 输出、日志或 zip 包。

## 4. 健康检查

```bash
curl "$QUANT_PLATFORM_API_URL/health"
```

返回示例：

```json
{
  "status": "ok",
  "service": "quant_platform_data_api"
}
```

## 5. Data API

研究员优先使用 `/data/*` 标准数据接口。

### 5.1 数据集列表

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/datasets"
```

### 5.2 数据覆盖

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/coverage"
```

### 5.3 数据字段

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/schema/prices_1d_pre"
```

### 5.4 查询数据

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/prices_1d_pre?start_date=2026-07-13&end_date=2026-07-13&order_book_id=000001.XSHE&fields=trade_date,order_book_id,close&limit=100"
```

常用参数：

```text
start_date      开始日期，YYYY-MM-DD
end_date        结束日期，YYYY-MM-DD
order_book_id   证券代码，多个用逗号分隔
fields          字段，多个用逗号分隔
limit           单次返回行数，最大 50000
offset          分页偏移
format          json 或 csv
```

支持数据集：

```text
trading_calendar
instruments
prices_1d_pre
prices_1d_none
index_prices_1d
tradability_1d
valuation_1d
industry_classification
index_components
index_weights
```

### 5.5 Python Client

复制或引用：

```text
examples/researcher_api_usage/quant_platform_client.py
```

示例：

```python
import os

from quant_platform_client import QuantPlatformClient

client = QuantPlatformClient(
    os.environ["QUANT_PLATFORM_API_URL"],
    os.environ["QUANT_PLATFORM_API_TOKEN"],
)

print(client.list_datasets())
print(client.get_coverage())

df = client.query_dataset(
    "prices_1d_pre",
    start_date="2026-07-13",
    end_date="2026-07-13",
    order_book_ids="000001.XSHE",
    fields=["trade_date", "order_book_id", "close"],
    limit=100,
)
print(df.head())
```

## 6. Backtest API

平台支持两种提交方式：

- `/backtests/run`：直接提交策略代码和配置。
- `/backtests/run-package`：提交标准 `strategy_package.zip`，推荐研究员使用。

### 6.1 提交 Strategy Package

```bash
curl -X POST \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -F "file=@strategy_package.zip" \
  "$QUANT_PLATFORM_API_URL/backtests/run-package"
```

成功后保存：

```text
run_id
dashboard URL
result zip 下载方式
```

查看：

```text
$QUANT_PLATFORM_API_URL/ui/backtests/runs/<run_id>
```

规范：

- 回测结果以 `run_id` 为准。
- `current` 只是最近一次回测，会被覆盖。
- 发给老板或同事时，优先发 `/ui/backtests/runs/<run_id>`。

### 6.2 查询历史 Runs

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/runs"
```

筛选：

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/runs?researcher_id=r001&limit=50"
```

### 6.3 查询单个 Run

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/runs/<run_id>/summary"
```

常用结果接口：

```text
GET /backtests/runs/{run_id}
GET /backtests/runs/{run_id}/summary
GET /backtests/runs/{run_id}/nav
GET /backtests/runs/{run_id}/positions
GET /backtests/runs/{run_id}/trades
GET /backtests/runs/{run_id}/orders
GET /backtests/runs/{run_id}/logs
GET /backtests/runs/{run_id}/download
```

## 7. Current Backtest API

`current` 表示最近一次结果，只适合快速查看。

```text
GET    /backtests/current
GET    /backtests/current/summary
GET    /backtests/current/nav
GET    /backtests/current/positions
GET    /backtests/current/trades
GET    /backtests/current/orders
GET    /backtests/current/logs
GET    /backtests/current/download
DELETE /backtests/current
```

规范：

- 不要把 `current` 当长期结果。
- 不要只保存 current 页面截图。
- 长期保存必须保存 `run_id` 和 result zip。

## 8. Paper Trading API

Paper Trading 是模拟盘，不是实盘，不接券商，不会真实下单。

Dashboard：

```text
$QUANT_PLATFORM_API_URL/ui/paper
$QUANT_PLATFORM_API_URL/ui/paper/<paper_id>
```

### 8.1 创建模拟账户

```bash
curl -X POST \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$QUANT_PLATFORM_API_URL/paper/accounts" \
  -d '{"paper_id":"demo_paper","strategy_name":"demo","initial_cash":1000000,"benchmark":"000300.XSHG"}'
```

### 8.2 上传 target_weights.csv

CSV 格式：

```csv
trade_date,order_book_id,target_weight
2026-07-13,000001.XSHE,0.5
2026-07-13,000002.XSHE,0.5
```

上传：

```bash
curl -X POST \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -F "file=@target_weights.csv" \
  "$QUANT_PLATFORM_API_URL/paper/accounts/<paper_id>/target-weights"
```

### 8.3 跑单日模拟

```bash
curl -X POST \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -H "Content-Type: application/json" \
  "$QUANT_PLATFORM_API_URL/paper/accounts/<paper_id>/run-daily" \
  -d '{"trade_date":"2026-07-13"}'
```

### 8.4 查询模拟账户

```text
GET /paper/accounts
GET /paper/accounts/{paper_id}
GET /paper/accounts/{paper_id}/nav
GET /paper/accounts/{paper_id}/positions
GET /paper/accounts/{paper_id}/trades
GET /paper/accounts/{paper_id}/orders
GET /paper/accounts/{paper_id}/logs
GET /paper/accounts/{paper_id}/download
```

## 9. Dashboard 页面

```text
/ui/data                    数据覆盖
/ui/backtests/runs          历史回测
/ui/backtests/runs/<run_id> 单个回测
/ui/researchers             研究员统计
/ui/paper                   模拟盘账户
/ui/paper/<paper_id>        单个模拟盘账户
```

Dashboard 页面本身主要用于浏览展示。下载接口仍需要 token。

## 10. 命名规范

### run_id

建议格式：

```text
<strategy_name>_<date_range>_<version>
```

示例：

```text
quality_value_2020_2026_v1
smallcap_momentum_2025_smoke
```

规范：

- 使用小写字母、数字、下划线。
- 不要包含空格、中文、路径符号。
- 不要复用旧 `run_id` 做不同策略。

### paper_id

建议格式：

```text
paper_<strategy_name>_<version>
```

示例：

```text
paper_quality_value_v1
paper_demo_001
```

### 文件名

- `strategy_package.zip`
- `target_weights.csv`
- `result_<run_id>.zip`

不要把 token、真实姓名、密码或敏感路径写入文件名。

## 11. 请求规范

- 单次 Data API 查询优先限制日期、股票池和字段。
- 大数据分页使用 `limit` + `offset`。
- 不要并发压测服务器。
- 不要循环请求全市场全历史。
- 不要把 API 返回的原始数据上传到公开仓库、公开网盘或未授权第三方工具。
- 自动化脚本必须设置合理 timeout。
- 失败时记录 endpoint、时间、参数范围和状态码，不记录 token。

## 12. 错误码

### 401 Unauthorized

常见原因：

- 没传 token。
- token 写错。
- Windows 使用了 Mac 的 `export`。
- Mac 使用了 Windows 的 `$env:`。

### 403 Forbidden

常见原因：

- token 已被禁用。
- 使用了旧 token。

### 404 Not Found

常见原因：

- URL 写错。
- endpoint 写错。
- `run_id` 或 `paper_id` 不存在。

### 410 Gone

常见原因：

- run registry 还在，但结果文件已过期或不可用。

### 422 Validation Error

常见原因：

- 请求参数格式不符合接口要求。
- 上传字段缺失。

### 500 Internal Server Error

常见原因：

- 服务端异常。
- 联系管理员，不要自己修服务器。

### 502 Bad Gateway

常见原因：

- API 后端未启动或异常。
- 联系管理员。

## 13. 安全规范

禁止：

- 在代码里硬编码真实 token。
- 把 token 写进 notebook 输出。
- 把 token 发到群聊或公开文档。
- 把 `.env`、私钥、密码、数据文件、结果 zip 提交到 Git。
- 让 Agent 读取 `.env`、私钥或真实账户配置。

推荐：

- 使用环境变量传 token。
- token 泄露后立即联系管理员禁用。
- 提交给 Agent 的 prompt 里写 `<管理员单独提供>`，不要贴真实 token。

## 14. 常用复制模板

Mac / Linux：

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="your_token_here"

curl "$QUANT_PLATFORM_API_URL/health"
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/datasets"
```

Windows PowerShell：

```powershell
$env:QUANT_PLATFORM_API_URL = "http://39.106.218.30"
$env:QUANT_PLATFORM_API_TOKEN = "your_token_here"

Invoke-RestMethod "$env:QUANT_PLATFORM_API_URL/health"
Invoke-RestMethod `
  -Headers @{ "X-API-Token" = $env:QUANT_PLATFORM_API_TOKEN } `
  "$env:QUANT_PLATFORM_API_URL/data/datasets"
```
