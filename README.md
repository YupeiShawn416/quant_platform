# quant_platform

内部量化投研平台 MVP。

当前主流程：

```text
Data API -> local research template -> weights package -> platform backtest -> Dashboard -> result zip
```

平台的定位不是让所有研究脚本都在服务器上运行。服务器负责统一数据服务、统一回测裁判、
统一结果展示和 Strategy Package 上传回测。研究员可以在本地电脑、Notebook 或 AI agent
项目中研究因子、信号和目标权重，但进入平台回测时必须提交标准 `strategy_package.zip`。

核心原则：

```text
因子可以自由研究，回测必须统一裁判。
```

## Current Platform Status

当前已经具备：

1. 2016-2026 本地 Parquet 数据湖
2. DuckDB 内存查询层
3. FastAPI 数据 API + researcher token
4. Python Client
5. DailyBacktestEngine V0
6. Result Bundle
7. Current Result 生命周期
8. `/backtests/run`
9. `/backtests/run-package`
10. Strategy Package `weights` mode
11. Dashboard current result MVP
12. Research weights template
13. VIX Q5 真实策略验收样例
14. Backtest Run Registry + run_id 独立结果查看
15. 2016 至今数据补全 workflow
16. 当前平台审计文档：`docs/PLATFORM_AUDIT_CURRENT_STATE.md`
17. Factor Library MVP：内置因子、因子分析、因子 Dashboard、因子生成 weights
18. Daily data update workflow：本地授权机器增量更新，服务器只读 Parquet
19. Multi-account Paper Trading MVP：多模拟账户、NAV、持仓、订单、成交、日志
20. API 使用手册与研究员交付文档
21. Intraday Snapshot Data workflow：固定 6 个日内快照点，不做全量分钟线
22. Research report data availability probe：研报字段可得性审计与回填优先级矩阵

## Current Stage

服务器部署、研究员 token、Data API、回测 Dashboard、Paper Trading MVP 和 Factor Library
MVP 已完成。当前主线是让研究员接入平台，并围绕数据 API、标准策略包、因子库和
paper trading 做协作开发与试运行。

研究员交付包：

```text
handoff/researcher_onboarding_2025/
```

入口文件：

- `handoff/researcher_onboarding_2025/00_READ_ME_FIRST.md`
- `handoff/researcher_onboarding_2025/02_SIMPLE_USER_MANUAL.md`
- `handoff/researcher_onboarding_2025/03_AI_AGENT_PROMPT.md`
- `handoff/researcher_onboarding_2025/08_AGENT_REPO_MIGRATION_RUNBOOK.md`

## Researcher Quick Links

服务器展示入口：

```text
http://39.106.218.30/ui/data
http://39.106.218.30/ui/backtests/runs
http://39.106.218.30/ui/researchers
http://39.106.218.30/ui/paper
http://39.106.218.30/ui/factors
```

研究员文档：

```text
handoff/researcher_onboarding_2025/
handoff/researcher_onboarding_2025/08_AGENT_REPO_MIGRATION_RUNBOOK.md
docs/RESEARCHER_DATA_API.md
docs/API_USAGE_MANUAL.md
docs/PAPER_TRADING_MVP.md
docs/FACTOR_LIBRARY_MVP.md
docs/RESEARCH_REPORT_DATA_AVAILABILITY_PROBE.md
```

## MVP Usage Flow

```bash
conda activate quant_platform
make install
make test
make api
```

研究员使用流程：

1. 通过 API 或 Python Client 拉取 2016-2026 标准数据。
2. 在本地研究项目中计算 factor / signal / weights。
3. 用 `research_weights_template` 生成 `strategy_package.zip`。
4. 上传到 `/backtests/run-package`。
5. 打开 Dashboard 查看 current result 或 run_id 独立结果。
6. 保存 run_id，并下载 result zip 长期保存。

## API Data Access

本地 API：

```text
http://127.0.0.1:8000
```

服务器 API：

```text
http://<server-ip-or-domain>
```

生产环境必须通过 `X-API-Token` 传 token：

```bash
curl -H "X-API-Token: <your_token>" \
  "http://127.0.0.1:8000/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume"
```

本地开发默认 `API_TOKEN=change_me` 时可以不传 token。研究员数据 API 见
`docs/RESEARCHER_DATA_API.md`，token 管理见 `docs/RESEARCHER_TOKEN_MANAGEMENT.md`。

## Researcher Workflow

推荐普通研究员使用 `research_weights_template`：

```bash
PYTHONPATH=src python scripts/20_create_research_project_from_template.py \
  --template weights \
  --name my_first_strategy \
  --output-dir /tmp \
  --force
```

进入项目后运行：

```bash
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
```

研究员主要修改：

- `configs/strategy.yaml`
- `src/strategy_research/factor.py`
- `src/strategy_research/signal.py`
- `src/strategy_research/portfolio.py`

不要随意修改标准字段名、Strategy Package 结构或平台结果格式。说明见
`docs/RESEARCHER_QUICKSTART.md` 和 `docs/RESEARCH_TEMPLATES.md`。

## Backtest And Dashboard

启动 API 后可以上传 Strategy Package：

```bash
curl -F "file=@/tmp/my_first_strategy_package.zip" \
  http://127.0.0.1:8000/backtests/run-package
```

Dashboard：

```text
http://127.0.0.1:8000/ui/backtests/current
http://127.0.0.1:8000/ui/backtests/runs
http://127.0.0.1:8000/ui/backtests/runs/<run_id>
http://127.0.0.1:8000/ui/data
http://127.0.0.1:8000/ui/researchers
```

下载当前结果：

```text
GET /backtests/current/download
```

`current` 仍代表最新结果，新回测会覆盖旧 current。每次回测也会写入 run registry，
研究员应保存自己的 run_id，并优先使用 `/ui/backtests/runs/<run_id>` 查看结果。
需要长期保存完整结果时，仍必须下载 result zip。

## Data Usage Policy

平台数据仅供内部学习、研究、回测、教学和策略验证使用。禁止外传原始行情数据、
接口返回数据、Parquet 文件、API token 或未脱敏的明细结果。详细制度见：

```text
docs/DATA_USAGE_POLICY.md
```

## 2025 MVP Acceptance

当前验收重点是使用 2025 数据跑通完整链路：

```text
data -> API -> template -> package -> backtest -> Dashboard -> result zip
```

验收清单见：

```text
docs/MVP_2025_ACCEPTANCE_CHECKLIST.md
```

VIX Q5 是真实验收样例，不是当前产品主线。它用于确认平台能力，不应继续把单一策略研究
当成平台建设主线。

## Server Deployment MVP

MVP 部署建议：

1. 本地授权机器负责 RQData 抓取和数据校验。
2. 用 `rsync` 把本地 Parquet 数据同步到服务器。
3. 服务器负责 API、Dashboard、回测和 result zip 下载。
4. 服务器默认不直接访问 RQData，除非确认授权、IP 白名单和 license 使用范围。

部署 checklist 见：

```text
docs/SERVER_DEPLOYMENT_RUNBOOK_MVP.md
docs/SERVER_DEPLOYMENT_SMOKE_TEST.md
docs/POST_DEPLOYMENT_RESEARCHER_TRIAL.md
docs/SERVER_DEPLOYMENT_MVP_CHECKLIST.md
docs/MVP_ROLLOUT_PLAN.md
```

当前正式数据支持区间：

```text
SUPPORTED_DATE_RANGE=2016-01-04 to latest complete data lake trading date
```

当前服务器已按数据湖覆盖动态识别可用结束日期。每日盘后更新流程先运行 dry-run：

```bash
make daily-update-dry-run END_DATE=<next_complete_trade_date>
```

确认计划无误后再由本地授权机器执行真实更新：

```bash
make daily-update END_DATE=<next_complete_trade_date>
make check-data-2016-present
make reconcile-daily-update
```

每日更新说明见：

```text
docs/DAILY_DATA_UPDATE.md
```

## Paper Trading MVP

平台现在支持多账户 Paper Trading MVP：研究员创建模拟账户，上传每日
`target_weights.csv`，平台按本地日频行情生成 NAV、持仓、订单、成交和日志。

入口：

```text
/ui/paper
/ui/paper/<paper_id>
```

本地 smoke：

```bash
make paper-smoke-local
```

说明见：

```text
docs/PAPER_TRADING_MVP.md
```

## Factor Library MVP

平台现在支持基础因子库 MVP：内置 5 个基础因子，支持因子计算、覆盖率/IC/分组收益/换手分析、Dashboard 展示，以及生成 long-only target weights。

入口：

```text
/ui/factors
/ui/factors/<factor_id>
```

本地 smoke：

```bash
make factor-smoke-local
```

说明见：

```text
docs/FACTOR_LIBRARY_MVP.md
```

## What Not To Do Yet

当前不要优先做：

- 复杂全量因子平台
- 复杂模拟交易 / 真实券商交易
- 复杂用户系统
- 服务器大规模直接访问 RQData
- 实时行情或分钟级行情
- 永久保存所有历史回测大文件
- 继续把 VIX Q5 策略深挖当成主线

这些能力应该在 MVP 上线试运行、研究员培训和 2025 验收之后再排期。

## Next Roadmap

推荐近期顺序：

1. 邀请研究员按 onboarding 文档接入平台。
2. 围绕 Data API 和 Factor Library 扩展更多标准因子。
3. 用标准 weights package 做回测验收。
4. 对值得持续跟踪的策略建立 paper account。
5. 每日盘后由本地授权机器更新数据，质量通过后再同步服务器。
6. 服务器数据同步后运行 `make paper-run-daily-all TRADE_DATE=<latest_complete_trade_date>`，
   推进所有 active paper accounts。

## How To Invite Contributors

协作者分两类：

1. 研究员：只需要 researcher onboarding、服务器地址和个人 API token。
2. 平台开发者：需要 GitHub 仓库权限、本地 conda 环境、测试命令和协作边界。

给研究员的入口：

```text
handoff/researcher_onboarding_2025/00_READ_ME_FIRST.md
handoff/researcher_onboarding_2025/08_AGENT_REPO_MIGRATION_RUNBOOK.md
docs/API_USAGE_MANUAL.md
docs/RESEARCHER_DATA_API.md
docs/PAPER_TRADING_MVP.md
docs/FACTOR_LIBRARY_MVP.md
docs/DAY_END_OPERATIONS.md
docs/INTRADAY_SNAPSHOT_DATA.md
```

给平台开发者的最小启动命令：

```bash
git clone <repo-url>
cd quant_platform
conda activate quant_platform
python -m pip install -e .
make test
make template-smoke
```

协作规则：

- 不提交 `.env`、真实 token、`data/`、`runs/`、Parquet、zip 或 `reports/generated/`。
- 不在服务器直接访问 RQData；数据更新由本地授权机器完成后同步。
- 新功能先补测试，再提交 PR。
- 回测、paper trading、factor library 的数据口径必须走平台标准 API 和数据湖。
- 研究员策略交付优先使用 `target_weights.csv` 或 `strategy_package.zip`。
