# Researcher Data API

研究员通过平台 Data API 拉取标准数据，用于本地研究、生成因子和构建 strategy package。

研究员不需要：

- RQData license
- 服务器密码
- 数据库账号
- 服务器文件权限

当前支持区间：

```text
2016-01-04 to 2026-07-10
```

服务器示例：

```text
http://39.106.218.30
```

不要在文档、代码、GitHub、聊天记录里写真实 token。

## 环境变量

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

Windows 不要照抄 `export`。Mac 不要照抄 `$env:`。

## 快速测试

Mac / Linux：

```bash
curl "$QUANT_PLATFORM_API_URL/health"

curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/datasets"
```

Windows PowerShell：

```powershell
Invoke-RestMethod "$env:QUANT_PLATFORM_API_URL/health"

Invoke-RestMethod `
  -Headers @{ "X-API-Token" = $env:QUANT_PLATFORM_API_TOKEN } `
  "$env:QUANT_PLATFORM_API_URL/data/datasets"
```

也可以使用 `curl.exe`：

```powershell
curl.exe -H "X-API-Token: $env:QUANT_PLATFORM_API_TOKEN" `
  "$env:QUANT_PLATFORM_API_URL/data/datasets"
```

PowerShell 里的 `curl` 可能是 alias，建议写 `curl.exe`。

## Datasets

- `trading_calendar`
- `instruments`
- `prices_1d_pre`
- `prices_1d_none`
- `index_prices_1d`
- `tradability_1d`
- `valuation_1d`
- `industry_classification`
- `index_components`
- `index_weights`
- `risk_free_rate`
- `financial_pit_field_pack`
- `financial_pit_quarterly`
- `intraday_snapshots`
- `cn_hxz_4_factors_monthly`
- `cn_ff3_factors_monthly`
- `hxz_monthly_research_panel`

注意：

- `prices_1d_pre`、`prices_1d_none` 和 `index_prices_1d` 当前完整价格覆盖到
  `2026-07-21`。
- 部分非价格类快照和财务 PIT 数据可覆盖到 `2026-07-22`。
- `intraday_snapshots` 是选定日期的快照数据，不是实时或分钟线服务。
- HXZ/FF3 数据集是实验研究数据。

## Endpoints

```text
GET /data/datasets
GET /data/coverage
GET /data/schema/{dataset}
GET /data/query/{dataset}
```

Query 参数：

```text
start_date=2026-07-13
end_date=2026-07-13
order_book_id=000001.XSHE,600519.XSHG
fields=trade_date,order_book_id,close
limit=5000
offset=0
format=json
```

`limit` 默认 `5000`，最大 `50000`。大结果用 `offset` 分页，不要一次拉整个数据湖。

CSV 输出：

```text
GET /data/query/prices_1d_pre?...&format=csv
```

## Python Client

复制或引用：

```text
examples/researcher_api_usage/quant_platform_client.py
examples/researcher_api_usage/data_api_quickstart.py
```

安装最小依赖：

```bash
pip install pandas requests
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

运行 quickstart：

```bash
python data_api_quickstart.py
```

Windows 和 Mac 都是这个 Python 命令，区别只在环境变量设置方式。
