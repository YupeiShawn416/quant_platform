# Researcher Quickstart: From Data API to Backtest Package

这份文档面向普通研究员、实习生和初级量化研究员。目标是用平台标准流程完成一次从数据到回测的
闭环。

研究员不需要自己写回测引擎，也不应该用自己计算的最终绩效替代平台结果。研究员负责研究因子、
信号和目标权重；平台负责统一回测、撮合、交易成本、绩效、结果包和 Dashboard。

## 1. Create A Research Project

在 quant_platform 仓库中运行：

```bash
PYTHONPATH=src python scripts/20_create_research_project_from_template.py \
  --template weights \
  --name my_first_strategy \
  --output-dir /tmp \
  --force
```

进入项目：

```bash
cd /tmp/my_first_strategy
```

## 2. Configure Strategy Metadata

主要修改：

```text
configs/strategy.yaml
```

设置 `strategy_id`、`strategy_name`、回测区间、初始资金、benchmark、组合参数等。

## 3. Fetch Or Prepare 2025 Data

模板默认使用确定性 demo 数据。真实研究可以通过平台 API、Python Client 或标准 Parquet
数据准备本地研究数据。

API 用法见：

```text
docs/API_DATA_ACCESS_GUIDE.md
```

## 4. Implement Factor

修改：

```text
src/strategy_research/factor.py
```

保持函数名不变：

```python
def compute_factor(market_data, config):
    ...
```

输出至少包含：

```text
trade_date
order_book_id
factor_value
```

## 5. Implement Signal

修改：

```text
src/strategy_research/signal.py
```

保持函数名不变：

```python
def generate_signal(factor_df, config):
    ...
```

输出至少包含：

```text
trade_date
order_book_id
signal_score
```

## 6. Implement Portfolio Weights

修改：

```text
src/strategy_research/portfolio.py
```

保持函数名不变：

```python
def generate_weights(signal_df, config):
    ...
```

输出至少包含：

```text
trade_date
order_book_id
target_weight
```

规则：

- long-only
- no negative weights
- no duplicate `trade_date + order_book_id`
- daily weight sum <= 1.0

## 7. Run The Workflow

```bash
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
```

成功后会生成：

```text
data/output/weights.csv
data/output/weights.parquet
strategy_package.zip
```

## 8. Upload To Platform

启动平台 API 后，在研究项目中运行：

```bash
python scripts/07_submit_package.py
```

或使用 curl：

```bash
curl -F "file=@/tmp/my_first_strategy_package.zip" \
  http://127.0.0.1:8000/backtests/run-package
```

生产环境需要加 token：

```bash
curl -H "X-API-Token: <your_token>" \
  -F "file=@/tmp/my_first_strategy_package.zip" \
  http://<server>/backtests/run-package
```

## 9. View Dashboard

打开：

```text
http://<server>/ui/backtests/current
```

本地开发一般是：

```text
http://127.0.0.1:8000/ui/backtests/current
```

## 10. Download Result Zip

从 Dashboard 左侧点击下载，或请求：

```text
GET /backtests/current/download
```

当前平台只保留一个 current，新回测会覆盖旧 current。需要长期保存结果时必须下载 result zip。

## 11. Write Research Conclusion

研究结论应至少说明：

- 策略逻辑
- 数据区间
- 因子定义
- 组合构建规则
- 回测结果摘要
- 风险和限制
- 是否有 benchmark warning

## 12. Do Not Change

除非非常清楚平台契约，不要改：

- `src/strategy_research/package_builder.py`
- 标准字段名
- Strategy Package 结构
- 平台回测结果格式
- result bundle 文件名
