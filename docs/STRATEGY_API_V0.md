# Strategy API V0

V0 策略是一个普通 Python 文件，必须提供：

```python
def generate_weights(context, data) -> dict[str, float]:
    ...
```

## context

`context` 是属性对象，包含：

```text
current_date
portfolio
config
trading_dates
previous_positions
```

## data

`data` 提供只读行情访问：

```text
get_price(symbol, field="close")
get_history(symbol, fields, window)
current_prices
```

## 返回值

返回目标权重：

```python
{
    "000001.XSHE": 0.2,
    "600519.XSHG": 0.3,
}
```

规则：

1. 返回目标权重，不是买卖信号。
2. 权重总和超过 1.0 时，V0 会等比例缩放。
3. 空 dict 表示清仓。
4. 只支持多头股票。
5. 不支持融资融券、期货、期权和盘中交易。

## 默认配置

```text
rebalance_frequency: daily
price_field: close
lot_size: 100
commission_rate: 0.0003
tax_rate: 0.001
slippage_rate: 0.0001
```

成交价 V0 默认使用当日 `close`。买入按 `close * (1 + slippage_rate)`，
卖出按 `close * (1 - slippage_rate)`。
