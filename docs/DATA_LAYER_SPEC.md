# Data Layer Spec

## Raw data lake

存储 RQData 原始行情、基础信息、指数、行业、市值、估值、财务、一致预期等。

当前本地数据湖是 Parquet 文件 + DuckDB 临时查询层，不是持久 DuckDB 数据库。
DuckDB 只在查询时读取 Parquet。

已落库或计划补全的数据集：

```text
instruments/instruments.parquet
trading_calendar/trading_calendar.parquet
prices_1d_pre/year=<year>.parquet
prices_1d_none/year=<year>.parquet
index_prices_1d/year=<year>.parquet
tradability_1d/year=<year>.parquet
valuation_1d/year=<year>.parquet
industry_classification/year=<year>.parquet
index_components/year=<year>.parquet
index_weights/year=<year>.parquet
```

Stage 25 introduces a resumable workflow to expand yearly partitions from 2016
to the latest available trading date. Until that workflow is executed and
quality-checked, the practical supported range remains the existing 2025 MVP
data.

股票行情和指数行情分开存储。`prices_1d_pre` / `prices_1d_none` 只放股票日频行情，
`index_prices_1d` 是 benchmark 的本地来源。
`tradability_1d` 是回测引擎的可交易性约束来源。
`valuation_1d` 是因子研究和组合诊断的市值/估值来源，暂不直接接入回测撮合。
`industry_classification`、`index_components`、`index_weights` 用于行业暴露、指数成分
重合度和相对 benchmark 诊断。

## Standard panel

标准化行情面板：

```text
trade_date
order_book_id
open
high
low
close
volume
amount
adjust_type
```

指数日频行情字段：

```text
trade_date
order_book_id
open
high
low
close
volume
total_turnover
num_trades
```

可交易性日频字段：

```text
trade_date
order_book_id
is_listed
is_suspended
is_st
can_buy
can_sell
reason
```

V0 的 `tradability_1d` 由本地交易日历、`instruments` 和股票日频行情派生：
缺少当日价格视为停牌，`special_type` 含 ST 视为不可买，`close >= limit_up`
视为不可买，`close <= limit_down` 视为不可卖。

市值估值日频字段：

```text
trade_date
order_book_id
market_cap
float_market_cap
pe_ratio
pb_ratio
ps_ratio
pcf_ratio
turnover_rate
```

V0 的 `valuation_1d` 来源：

```text
market_cap        <- RQData factor market_cap
float_market_cap  <- RQData factor market_cap_2
pe_ratio          <- RQData factor pe_ratio
pb_ratio          <- RQData factor pb_ratio
ps_ratio          <- RQData factor ps_ratio
pcf_ratio         <- RQData factor pcf_ratio
turnover_rate     <- RQData get_turnover_rate(today)
```

行业分类字段：

```text
trade_date
order_book_id
industry_system
industry_level
industry_code
industry_name
```

V0 默认使用 `citics_2019` 一级行业。

指数成分字段：

```text
trade_date
index_id
order_book_id
```

指数权重字段：

```text
trade_date
index_id
order_book_id
weight
```

V0 默认覆盖：

```text
000300.XSHG
000905.XSHG
000852.XSHG
```

## Derived feature panel

收益率、风险暴露和交易行为派生特征：

```text
ret_1d
fwd_ret_1d
fwd_ret_5d
fwd_ret_20d
volatility
beta
turnover
momentum
market_cap
```

收益率可以由行情统一计算，不一定直接从 RQData 抓。市场 Beta 是派生特征或风险暴露，
不是最底层原始数据。

## Factor store

保存研究因子值，支持版本、权限、追溯和追加更新。

## Signal/weight store

保存交易信号和目标权重。研究员应通过数据中台拿标准数据，不要每个人重复定义数据口径。

## China HXZ replication audit

HXZ 四因子复现需要比普通因子研究更严格的数据口径，尤其是财报的 point-in-time
可得性和公告日期。当前本地数据湖已经支持：

```text
daily unadjusted / pre-adjusted prices
daily market_cap / float_market_cap
daily tradability / ST / suspension flags
industry classification
listing / delisting fields from instruments
index prices and index membership
```

当前本地数据湖仍缺少：

```text
PIT annual total assets
PIT quarterly profit
PIT book equity / parent equity
real financial statement announcement date
RMB risk-free rate
materialized monthly HXZ input panel
```

运行以下命令可生成本地审计报告和字段矩阵：

```bash
make hxz-data-audit
```

如需探测 RQData 财报/因子接口，先在当前 shell 设置 `RQDATAC_KEY`，再运行：

```bash
make hxz-rqdata-probe
```

探针只做小样本接口确认，不会批量下载全量财务字段。

HXZ P0 原始数据回填 dry-run 使用三个目标数据集：

```text
financial_pit_quarterly
financial_factor_daily_pit
risk_free_rate
```

其中 `financial_pit_quarterly` 来自 `rqdatac.get_pit_financials_ex`，必须保留
`quarter`、`info_date`、`rice_create_tm`、`if_adjusted` 等 PIT 和版本字段。
`financial_factor_daily_pit` 来自 `rqdatac.get_factor` 的 `_mrq_0` / `_lyr_0`
字段，用于日频可见值面板。`risk_free_rate` 来自 `rqdatac.get_yield_curve`。

`monthly_hxz_inputs` 是后续派生层，不属于 P0 原始回填。
