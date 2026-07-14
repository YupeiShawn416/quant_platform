# Multi Paper Trading MVP

Paper Trading MVP 用来让研究员把每日 `target_weights.csv` 放到平台上，按本地日频行情做简单模拟账户跟踪。

展示入口：

```text
http://39.106.218.30/ui/paper
http://39.106.218.30/ui/paper/<paper_id>
```

`demo_paper_001` 只是 demo account，不代表真实策略。

## 它不是什么

- 不是实盘。
- 不连接券商。
- 不下真实订单。
- 不做实时行情。
- 不做分钟级撮合。
- 不自动定时运行。

## 多账户

多个 paper account 可以并行存在。老板或研究员可以在 `/ui/paper` 看到账户列表，在
`/ui/paper/<paper_id>` 查看单个账户的 summary、NAV、持仓、订单、成交、日志和下载链接。

## target_weights.csv

目标权重 CSV 必须包含：

```csv
trade_date,order_book_id,target_weight
2026-07-13,000001.XSHE,0.5
2026-07-13,000002.XSHE,0.5
```

规则：

- `trade_date` 必须在当前支持区间 `2016-01-04` 到 `2026-07-10` 内。
- 同一交易日权重合计不能超过 `1.0`。
- 不允许重复的 `trade_date + order_book_id`。
- 股票代码必须存在于平台 instruments 数据。

研究员交接时，只需要把 `target_weights.csv`、策略说明和希望使用的 `paper_id` 交给管理员或 Agent。

## API 流程

创建账户：

```bash
curl -X POST "$QUANT_PLATFORM_API_URL/paper/accounts" \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"paper_id":"demo_paper","strategy_name":"demo","initial_cash":1000000,"benchmark":"000300.XSHG"}'
```

上传目标权重：

```bash
curl -X POST "$QUANT_PLATFORM_API_URL/paper/accounts/demo_paper/target-weights" \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -F "file=@target_weights.csv"
```

运行单日：

```bash
curl -X POST "$QUANT_PLATFORM_API_URL/paper/accounts/demo_paper/run-daily" \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"trade_date":"2026-07-10"}'
```

查看：

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

## 本地 smoke

不依赖 RQData，不写真实数据湖：

```bash
make paper-smoke-local
```

如果本地 API 已启动，也可以使用 demo 脚本：

```bash
make create-demo-paper-account
make submit-demo-paper-weights
make run-demo-paper-daily
```

## 不要提交

不要提交以下运行产物：

```text
runs/
*.zip
*.parquet
reports/generated/
```
