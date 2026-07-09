# MVP 2025 Acceptance Checklist

用 2025 数据验收完整平台流程：

```text
data -> API -> research template -> strategy package -> backtest -> Dashboard -> result zip
```

每一项建议记录：

```text
Status:
Owner:
Notes:
Fix Plan:
```

## A. 数据层验收

- [ ] instruments 可读
- [ ] trading_calendar 可读
- [ ] prices_1d_pre 可读
- [ ] prices_1d_none 可读
- [ ] index_prices_1d 可读，当前应包含 2025 六个常用指数
- [ ] tradability_1d 可读
- [ ] valuation_1d 可读
- [ ] industry_classification 可读
- [ ] index_components / index_weights 可读
- [ ] `make check-data` 通过
- [ ] `make check-index-data` 通过
- [ ] 数据质量检查没有 blocker

## B. API 验收

- [ ] `/health` 通过
- [ ] `/status` 通过
- [ ] `/instruments` 可返回数据
- [ ] `/calendar` 可返回数据
- [ ] `/prices` 可返回数据
- [ ] `/data-quality` 可返回结果
- [ ] token 鉴权有效
- [ ] Python Client 可用

## C. Research Template 验收

- [ ] 可以从模板创建新项目
- [ ] `01_load_data.py` 可运行
- [ ] `02_compute_factor.py` 可运行
- [ ] `03_generate_signal.py` 可运行
- [ ] `04_generate_weights.py` 可运行
- [ ] `05_validate_outputs.py` 可运行
- [ ] `06_build_package.py` 可运行
- [ ] 能生成 `weights.csv`
- [ ] 能生成 `weights.parquet`
- [ ] 能生成 `strategy_package.zip`

## D. Backtest 验收

- [ ] `/backtests/run-package` 可成功
- [ ] current summary 可读
- [ ] current nav 可读
- [ ] current trades 可读
- [ ] current positions 可读
- [ ] current logs 可读
- [ ] current download 可用

## E. Dashboard 验收

- [ ] overview 页面可打开
- [ ] nav 页面可打开
- [ ] account 页面可打开
- [ ] positions 页面可打开
- [ ] trades 页面可打开
- [ ] orders 页面可打开
- [ ] logs 页面可打开
- [ ] result zip 可下载

## F. 研究样例验收

- [ ] demo weights package 跑通
- [ ] VIX Q5 pilot 跑通
- [ ] 至少再准备一个简单动量/反转样例，后续可做

## G. 结果文件验收

- [ ] result zip 包含 `summary.json`
- [ ] result zip 包含 `nav.csv`
- [ ] result zip 包含 `trades.csv`
- [ ] result zip 包含 `positions.csv`
- [ ] result zip 包含 `orders.csv`
- [ ] result zip 包含 `logs.txt`
- [ ] summary 指标可读
- [ ] 如果 benchmark 缺失，必须 warning
- [ ] 如果 benchmark 已有，必须是真实 benchmark_nav

## H. 教学验收

- [ ] 一名研究员能按文档完成完整流程
- [ ] 一名 AI agent 能按 `AGENTS.md` 修改模板并生成 package
- [ ] 研究员能解释 result zip 和 Dashboard 指标
- [ ] 研究员理解 current 会被覆盖，长期保存必须下载 zip
- [ ] 研究员理解数据使用规范

## I. 不通过项记录

| Item | Status | Owner | Notes | Fix Plan |
|---|---|---|---|---|
|  |  |  |  |  |
