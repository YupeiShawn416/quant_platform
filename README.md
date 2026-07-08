# quant_platform

内部量化投研数据平台 MVP。

当前主链路：

```text
RQData -> Parquet -> DuckDB -> ResearchDataLoader -> FastAPI
```

## 当前已完成能力

1. RQData license 连接检查
2. 小样本数据落盘
3. 2025 全 A 日频数据落盘
4. Parquet 数据湖
5. DuckDB 本地查询
6. FastAPI 本地数据服务
7. 标准回测结果包
8. 自研日频回测引擎 V0

## 本地运行方式

```bash
conda activate quant_platform
make install
make test
make api
```

另一个终端运行 API smoke test：

```bash
conda activate quant_platform
make api-smoke
```

## 常用接口

```text
GET /health
GET /status
GET /instruments
GET /calendar
GET /prices
GET /data-quality
GET /backtests
GET /backtests/{run_id}/summary
GET /backtests/{run_id}/nav
GET /backtests/{run_id}/trades
GET /backtests/{run_id}/positions
GET /backtests/{run_id}/download
POST /backtests/run
GET /backtests/current
GET /backtests/current/summary
GET /backtests/current/nav
GET /backtests/current/trades
GET /backtests/current/positions
GET /backtests/current/download
```

行情查询示例：

```bash
curl "http://127.0.0.1:8000/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume"
```

## Python Client 使用方式

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

本地开发默认 `API_TOKEN=change_me`，可不传 token。部署到服务器时必须设置强
token，并通过 `X-API-Token` 调用。

## Deployment Preparation

部署预备说明见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)。

本地可先运行：

```bash
make deploy-check
make api-prod
```

## Backtest Demo

```bash
make demo-daily-backtest
make view-demo-daily-backtest
make backtest-api-smoke
```

结果写入 `runs/backtests/demo_daily_backtest/`，该目录不会提交到 Git。
通过 API 提交的最新结果写入 `runs/backtests/current/`，新回测会覆盖旧 current。

## Backtest Dashboard

```bash
make api
make backtest-api-smoke
make dashboard-smoke
```

打开：

```text
http://127.0.0.1:8000/ui/backtests/current
```

## Strategy Package V1

推荐研究员使用 `weights` 模式：线下完成因子、信号和组合构建，导出标准
`weights.parquet`：

```text
trade_date
order_book_id
target_weight
```

高级用户可以使用 `code` 模式上传 `strategy.py`，但生产环境必须走 Docker 沙箱。

本地 demo：

```bash
make create-demo-weights-package
make api
make submit-demo-weights-package
make dashboard-smoke
```

上传成功后打开 dashboard 查看 current 回测，并通过页面下载 result zip。

## 数据安全

1. `.env` 不提交
2. `data/` 不提交
3. RQData license 不打印
4. API token 不打印
5. Parquet 本地数据不进 Git

## 下一步计划

1. 回补 2024 / 2023 日频数据
2. 实现每日增量更新
3. 增强 API 权限、审计和限流
4. 增加 RQAlpha bundle 和 runner 对接
5. 增加每日模拟盘
6. 部署到阿里云服务器
