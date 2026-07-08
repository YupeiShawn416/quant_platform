# Data Layer Spec

## Raw data lake

存储 RQData 原始行情、基础信息、指数、行业、市值、估值、财务、一致预期等。

当前本地数据湖是 Parquet 文件 + DuckDB 临时查询层，不是持久 DuckDB 数据库。
DuckDB 只在查询时读取 Parquet。

已落库的数据集：

```text
instruments/instruments.parquet
trading_calendar/trading_calendar.parquet
prices_1d_pre/year=2025.parquet
prices_1d_none/year=2025.parquet
index_prices_1d/year=2025.parquet
tradability_1d/year=2025.parquet
```

股票行情和指数行情分开存储。`prices_1d_pre` / `prices_1d_none` 只放股票日频行情，
`index_prices_1d` 是 benchmark 的本地来源。
`tradability_1d` 是回测引擎的可交易性约束来源。

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
