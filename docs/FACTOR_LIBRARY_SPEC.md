# Factor Library Spec

## 因子元数据

```text
factor_id
factor_name
category
tags
description
author
source_data
calculation_logic
frequency
universe
direction
higher_is_better
winsorization_method
standardization_method
neutralization_method
version
created_at
updated_at
```

## 因子值长表

```text
trade_date
order_book_id
factor_id
factor_value
factor_version
```

长表用于入库、版本控制、权限管理和追加更新。

## 因子值宽表

```text
trade_date
order_book_id
factor_a
factor_b
factor_c
```

宽表用于研究检查、看板、相关性矩阵和机器学习建模。

## 因子分类

```text
价格动量类：momentum / reversal / trend
波动风险类：volatility / beta / drawdown
流动性类：turnover / volume / amount / illiquidity
规模市值类：market_cap / float_cap
估值类：PE / PB / PS / EV
成长类：revenue_growth / profit_growth
质量类：ROE / margin / leverage / accrual
分析师预期类：consensus / revision / surprise
资金行为类：northbound / institutional / fund_flow
事件类：limit_up / earnings / restructuring
另类数据类：news / sentiment / forum / ESG
自定义研究类：experimental
```

## 因子相关性检查

```text
因子值截面相关性
RankIC 相关性
分年度相关性
分市场状态相关性
同类因子相关性
跨类因子相关性
与风格因子的相关性
中性化后相关性
聚类图 / 热力图
```

目标不是避免因子正交，而是避免重复研究高度相关、信息重叠的因子。低相关或正交因子
反而可能有组合价值。
