# API Data Access Guide

本文说明研究员如何通过 quant_platform API 获取数据用于本地研究。

## 1. Base URL

本地：

```text
http://127.0.0.1:8000
```

服务器：

```text
http://<server-ip-or-domain>
```

## 2. API Token

生产环境使用 Header：

```text
X-API-Token: <your_token>
```

本地开发中，如果 `API_TOKEN=change_me`，平台允许不传 token。不要把 token 写入代码仓库、
公开文档或聊天记录。

## 3. Check Health And Status

```bash
curl http://127.0.0.1:8000/health
```

```bash
curl -H "X-API-Token: <your_token>" \
  http://127.0.0.1:8000/status
```

`/status` 返回当前关键本地数据文件是否存在及行数。

## 4. Fetch Instruments

```bash
curl -H "X-API-Token: <your_token>" \
  "http://127.0.0.1:8000/instruments?limit=20"
```

## 5. Fetch Calendar

```bash
curl -H "X-API-Token: <your_token>" \
  "http://127.0.0.1:8000/calendar?start=2025-01-02&end=2025-01-31"
```

## 6. Fetch 2025 Stock Prices

实际 endpoint 参数是：

```text
symbols
start
end
adjust_type
fields
```

示例：

```bash
curl -H "X-API-Token: <your_token>" \
  "http://127.0.0.1:8000/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-31&adjust_type=pre&fields=open,close,volume"
```

限制：

- `adjust_type` 只允许 `pre` 或 `none`
- 单次日期跨度不超过 366 天
- 单次最多 200 个 symbols

## 7. Python requests Example

```python
import os
import pandas as pd
import requests

base_url = os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000")
token = os.environ.get("QUANT_PLATFORM_API_TOKEN")
headers = {"X-API-Token": token} if token else {}

response = requests.get(
    f"{base_url}/prices",
    params={
        "symbols": "000001.XSHE,600519.XSHG",
        "start": "2025-01-02",
        "end": "2025-01-31",
        "adjust_type": "pre",
        "fields": "open,close,volume",
    },
    headers=headers,
    timeout=30,
)
response.raise_for_status()
df = pd.DataFrame(response.json()["data"])
df.to_csv("prices_sample.csv", index=False)
```

## 8. Python Client Example

```python
import os

from rq_platform.client import QuantPlatformClient

client = QuantPlatformClient(
    base_url=os.environ.get("QUANT_PLATFORM_API_URL", "http://127.0.0.1:8000"),
    token=os.environ.get("QUANT_PLATFORM_API_TOKEN"),
)

status = client.status()
prices = client.get_prices(
    symbols=["000001.XSHE", "600519.XSHG"],
    start="2025-01-02",
    end="2025-01-31",
    adjust_type="pre",
    fields=["open", "close", "volume"],
)

prices.to_parquet("prices_sample.parquet", index=False)
```

## 9. Data Scope

当前主要可用数据范围是 2025：

- instruments
- trading calendar
- A-share daily stock prices, `pre` and `none`
- index prices
- tradability
- valuation
- industry classification
- index components and weights

后续扩展到 2016 至今后，API 可以服务更长历史研究。

## 10. Request Discipline

保守建议：

- 不要并发请求。
- 不要循环暴力拉取全市场。
- 优先按日期范围和股票池过滤。
- 大数据量需求先联系管理员，使用离线数据包或标准 Parquet。
- 不要把 API 当成对外数据服务。

## 11. Data Usage Warning

拉取数据仅限内部学习、研究、回测、教学和策略验证。禁止外传，禁止泄露 token，禁止把数据上传
到公开仓库、公开网盘、公开 AI 工具或未授权第三方服务。详细规则见：

```text
docs/DATA_USAGE_POLICY.md
```
