# Python Client

## 安装本地包

```bash
make install
```

## 启动 API

```bash
make api
```

## Python client 示例

```python
from rq_platform.client import QuantPlatformClient

client = QuantPlatformClient(
    base_url="http://127.0.0.1:8000",
    token=None,
)

df = client.get_prices(
    symbols=["000001.XSHE", "600519.XSHG"],
    start="2025-01-02",
    end="2025-01-10",
    adjust_type="pre",
    fields=["open", "close", "volume"],
)

print(df.head())
```

## 环境变量

```text
QUANT_PLATFORM_API_URL
QUANT_PLATFORM_API_TOKEN
```

## Smoke test

```bash
make client-smoke
```

Client 不直接读取 parquet，只请求 HTTP API。本地开发默认 `API_TOKEN=change_me`，
可以不传 token；部署环境应设置强 token，并通过 `X-API-Token` 访问 API。
