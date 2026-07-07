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
```

行情查询示例：

```bash
curl "http://127.0.0.1:8000/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume"
```

## 数据安全

1. `.env` 不提交
2. `data/` 不提交
3. RQData license 不打印
4. Parquet 本地数据不进 Git

## 下一步计划

1. 回补 2024 / 2023 日频数据
2. 实现每日增量更新
3. 增加 API token 鉴权
4. 增加 RQAlpha bundle 和回测 runner
5. 增加每日模拟盘
6. 部署到阿里云服务器
