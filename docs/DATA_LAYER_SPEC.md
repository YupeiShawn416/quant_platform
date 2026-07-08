# Data Layer Spec

## Raw data lake

存储 RQData 原始行情、基础信息、指数、行业、市值、估值、财务、一致预期等。

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
