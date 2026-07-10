# MVP Rollout Plan

## Phase 1: Local MVP Complete

当前状态：

- 2025 本地数据
- FastAPI 数据服务
- Python Client
- DailyBacktestEngine V0
- Result Bundle
- Current Result
- Strategy Package `weights` mode
- `/backtests/run-package`
- Dashboard current result MVP
- Backtest Run Registry + run_id result view
- Research templates
- VIX Q5 pilot

VIX Q5 是验收样例，不是平台建设主线。

## Phase 2: Server Deployment Trial

Stage 21 documentation is complete. Stage 22 is the server deployment MVP
preparation step: runbook, smoke test, data sync procedure, and researcher trial
plan.

目标：

- 轻量云或 ECS 部署
- 本地数据 `rsync` 到服务器
- 服务器运行 API / Dashboard / backtest
- 暂时不让服务器直接访问 RQData
- 用 2025 数据完成验收

服务器角色：

- 统一数据服务
- 统一回测裁判
- 统一结果展示
- Strategy Package 上传回测

服务器不是所有研究脚本的统一运行环境。

## Phase 3: Researcher Trial

This should happen after the server smoke test passes.

目标：

- 选择 1-3 名研究员
- 跑 demo package
- 跑 VIX Q5 acceptance sample
- 跑一个简单动量或反转样例
- 确认每个参与者能保存 run_id 并打开自己的 run detail 页面
- 收集文档、模板、API、Dashboard 反馈
- 修正文档和模板

## Phase 4: Data Expansion

目标扩展到 2016 至今：

- 股票行情
- 指数行情
- 可交易性
- 估值
- 行业
- 指数成分
- 指数权重
- 派生特征

数据扩展应保留质量检查和 update log，不要只追求落盘速度。

Stage 25 provides the resumable backfill workflow. Do not mark 2016-present as
supported until `make audit-data-lake`, full backfill, and
`make check-data-2016-present` pass.

## Phase 5: Daily ETL

目标：

- 每日更新脚本
- 质量检查
- update log
- 失败重试和告警
- 先本地授权机器抓取，再同步服务器
- 后续确认授权后再考虑服务器自动抓取

## Phase 6: Platform Upgrade

后续能力：

- 多 run 对比
- 本地 viewer
- 用户管理
- 权限管理
- 模拟交易 / Paper Trading
- 因子库

## Near-Term Recommendation

下一步主线不是继续深挖 VIX Q5，也不是马上做大型功能。建议先完成：

1. 部署 Stage 24 到服务器。
2. 让研究员按 run_id 查看自己的结果。
3. 按 `docs/POST_DEPLOYMENT_RESEARCHER_TRIAL.md` 组织 1-3 名研究员试运行。
4. 根据试运行反馈修正文档和模板。
5. 再扩展 2016 至今数据和每日 ETL。
