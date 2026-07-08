# Strategy Package V1

V1 支持三种策略包模式，主路径是 `weights` 模式。

## A. weights 模式

```text
strategy_package.zip
├── manifest.json
├── config.json
├── weights.parquet
├── weights.csv
├── README.md
├── factor_snapshot.parquet
└── signal_snapshot.parquet
```

研究员在线下完成数据读取、因子计算、信号生成和组合构建，导出每日目标权重。
平台统一负责权重校验、交易约束、撮合、绩效和标准结果包。

## B. signals 模式

```text
strategy_package.zip
├── manifest.json
├── config.json
├── signals.parquet
└── README.md
```

`signals.parquet` 字段：

```text
trade_date
order_book_id
signal_score
```

V1 只定义标准，执行暂未实现。

## C. code 模式

```text
strategy_package.zip
├── manifest.json
├── config.json
├── strategy.py
├── requirements.txt
├── factors/
└── README.md
```

`strategy.py` 必须提供：

```python
def generate_weights(context, data) -> dict[str, float] | None:
    ...
```

生产环境必须走 Docker 沙箱。`requirements.txt` 只做白名单校验，不自动安装。

## manifest.json

```json
{
  "package_version": "1.0",
  "strategy_id": "vix_beta_q5_long_only",
  "strategy_name": "VIX Beta Q5 Long Only",
  "author": "researcher_name",
  "mode": "weights",
  "created_at": "2026-07-08",
  "description": "Q5 long-only portfolio based on VIX beta score."
}
```

`strategy_id` 只允许小写字母、数字、下划线和短横线。manifest 不允许指定本地路径、
shell command 或外部 URL 依赖。

## weights 文件

推荐 `weights.parquet`，也支持 `weights.csv`。必须是长表：

```text
trade_date
order_book_id
target_weight
```

可选字段：

```text
symbol
signal_score
factor_value
rank
group
rebalance_flag
note
```

校验规则：日期可解析、股票代码非空、权重数值且非负、同日同票不重复、单日权重和
不超过 1.0 + tolerance。`allow_weight_normalization=true` 时可以等比例缩放并产生 warning。

## weight_mode

`daily_target`：文件中出现的日期按目标权重调仓，未出现日期目标为空仓。

`rebalance_only`：文件中出现的日期调仓，未出现日期返回 `None`，表示继续持有。
