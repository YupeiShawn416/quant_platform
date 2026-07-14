# Factor Library MVP

Factor Library MVP 用来把平台从“能跑策略”推进到“能系统化研究因子”。

第一版只做内置基础因子、因子落盘、因子分析、Dashboard 展示，以及从因子生成 long-only target weights。

## 内置因子

| factor_id | 含义 | 数据 | score 方向 |
| --- | --- | --- | --- |
| `market_cap` | 市值因子 | `valuation_1d` | 小市值高分 |
| `turnover_rate` | 换手率因子 | `valuation_1d` | 低换手高分 |
| `momentum_20d` | 20 日动量 | `prices_1d_pre` | 高动量高分 |
| `reversal_5d` | 5 日反转 | `prices_1d_pre` | 近 5 日跌幅大高分 |
| `volatility_20d` | 20 日波动率 | `prices_1d_pre` | 低波动高分 |

## factor_value 与 factor_score

- `factor_value` 是原始因子值。
- `factor_score` 是横截面处理后的分数，用于排序、分组和生成权重。
- MVP 默认使用 1%/99% winsorize，然后做按日横截面 zscore。
- 行业中性化暂不做，后续再加。

## 计算因子

```bash
make compute-builtin-factors START_DATE=2026-05-01 END_DATE=2026-07-10
```

指定因子：

```bash
make compute-builtin-factors START_DATE=2026-05-01 END_DATE=2026-07-10 FACTOR_IDS=momentum_20d,market_cap
```

输出：

```text
data/factor_library/values/<factor_id>/year=<year>/factor_values.parquet
```

`data/factor_library/` 是运行产物，不提交 Git。

## 分析因子

```bash
make analyze-factor FACTOR_ID=momentum_20d
```

输出：

```text
data/factor_library/analysis/<factor_id>/factor_summary.json
data/factor_library/analysis/<factor_id>/factor_summary.md
data/factor_library/analysis/<factor_id>/ic_daily.csv
data/factor_library/analysis/<factor_id>/group_returns.csv
data/factor_library/analysis/<factor_id>/group_nav.csv
data/factor_library/analysis/<factor_id>/turnover.csv
data/factor_library/analysis/<factor_id>/coverage.csv
data/factor_library/analysis/<factor_id>/top_bottom_latest.csv
```

分析指标：

- 覆盖率、缺失率
- 极值统计
- IC / Rank IC
- 分组收益
- 分组 NAV
- top group - bottom group
- top quantile 换手
- 最新 top/bottom stocks

## Dashboard

```text
/ui/factors
/ui/factors/<factor_id>
```

列表页显示因子元数据和分析摘要。详情页显示因子描述、处理方式、IC、分组收益、NAV、换手和最新 top/bottom。

## 生成 weights

```bash
make generate-factor-weights FACTOR_ID=momentum_20d
```

输出：

```text
runs/factor_weights/<factor_id>_<timestamp>/target_weights.csv
runs/factor_weights/<factor_id>_<timestamp>/manifest.json
runs/factor_weights/<factor_id>_<timestamp>/README.md
```

`target_weights.csv` 字段：

```text
trade_date
order_book_id
target_weight
```

这些 weights 是 long-only、无杠杆、非空头，可以接入现有 weights package、回测或 paper trading。

## API

```text
GET  /factors
GET  /factors/{factor_id}
GET  /factors/{factor_id}/ic
GET  /factors/{factor_id}/groups
GET  /factors/{factor_id}/nav
GET  /factors/{factor_id}/turnover
GET  /factors/{factor_id}/top-bottom
POST /factors/{factor_id}/generate-weights
```

部署环境需要 `X-API-Token`。

## 本地 smoke

不调用 RQData，不访问公网：

```bash
make factor-smoke-local
```

## 当前限制

- 只支持 5 个内置因子。
- 暂不做表达式系统。
- 暂不做在线因子编辑器。
- 暂不做机器学习因子挖掘。
- 暂不做行业中性化。
- 第一版 universe 优先支持 `all`；`csi300/csi500` 依赖 `index_components` 字段完整性。

## 后续计划

- 因子表达式 DSL。
- 行业和市值中性化。
- 因子组合。
- 因子权限和发布流程。
- 因子研究报告导出。
