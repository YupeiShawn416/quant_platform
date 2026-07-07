# API

## 启动 API

```bash
make api
```

## 健康检查

```bash
curl "http://127.0.0.1:8000/health"
```

## 查看本地数据状态

```bash
curl "http://127.0.0.1:8000/status"
```

## 查询行情

```bash
curl "http://127.0.0.1:8000/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume"
```

参数说明：

```text
symbols: 逗号分隔股票代码
start: 开始日期
end: 结束日期
adjust_type: pre 或 none
fields: 逗号分隔字段
```

## 查看数据质量

```bash
curl "http://127.0.0.1:8000/data-quality?year=2025"
```

## 注意事项

当前 API 只读本地 Parquet，不会实时请求 RQData。使用前需要先保证
`data/research_data/rqdata` 下有本地数据。
