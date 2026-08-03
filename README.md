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

Last audited: 2026-08-03.

当前已经具备：

1. 2010 起核心日频 Parquet 数据湖
2. DuckDB 内存查询层
3. FastAPI 通用 Data API + researcher token
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
21. Intraday Snapshot Data workflow：固定日内快照点，不做全量分钟线
22. Research report data availability probe：研报字段可得性审计与回填优先级矩阵
23. Financial PIT Field Pack workflow：基于已验证字段扩展财务 PIT 原始字段包
24. Financial Cash-flow Field Pack workflow：现金流 PIT 与 TTM 现金流字段包
25. Handoff onboarding pack v0.4：生成最新 Strategy Package V1 `weights` 包

## Current Stage

服务器部署、研究员 token、Data API、回测 Dashboard、Paper Trading MVP、Factor
Library MVP 和 researcher handoff v0.4 已完成。当前主线是把平台从 MVP 试运行推进到
可持续协作产品：让研究员和 agent 稳定使用 Data API、本地研究模板、标准策略包、因子库和
paper trading，同时补齐数据治理、批量查询、回测可信度和运维自动化。

研究员交付包：

```text
handoff/researcher_onboarding_2025/
handoff/researcher_onboarding_v0.4.zip
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
docs/FINANCIAL_PIT_FIELD_PACK.md
```

## MVP Usage Flow

```bash
conda activate quant_platform
make install
make test
make api
```

研究员使用流程：

1. 通过 API 或 Python Client 拉取标准数据。
2. 在本地研究项目中计算 factor / signal / weights。
3. 用 `research_weights_template` 或 handoff v0.4 样板生成 `strategy_package.zip`。
4. 上传到 `/backtests/run-package`。
5. 打开 Dashboard 查看 current result 或 run_id 独立结果。
6. 保存 run_id，并下载 result zip 长期保存。

当前推荐的 handoff 包是：

```text
handoff/researcher_onboarding_v0.4.zip
```

Strategy Package V1 `weights` 模式要求权重列为：

```text
trade_date
order_book_id
target_weight
```

## API Data Access

本地 API：

```text
http://127.0.0.1:8000
```

服务器 API：

```text
http://39.106.218.30
```

生产环境必须通过 `X-API-Token` 传 token：

```bash
curl -H "X-API-Token: <your_token>" \
  "http://39.106.218.30/data/query/prices_1d_pre?start_date=2026-07-31&end_date=2026-07-31&fields=trade_date,order_book_id,close,volume&limit=50000"
```

本地开发默认 `API_TOKEN=change_me` 时可以不传 token。研究员数据 API 见
`docs/RESEARCHER_DATA_API.md`，token 管理见 `docs/RESEARCHER_TOKEN_MANAGEMENT.md`。

通用 Data API：

```text
GET /data/datasets
GET /data/coverage
GET /data/schema/{dataset}
GET /data/query/{dataset}
```

单次查询默认 `limit=5000`，最大 `limit=50000`。大结果优先用 `format=csv`，并用
`offset` 分页。小样本和 agent 调试可以用 JSON。

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

固定 run_id 结果接口：

```text
GET /backtests/runs
GET /backtests/runs/{run_id}
GET /backtests/runs/{run_id}/summary
GET /backtests/runs/{run_id}/nav
GET /backtests/runs/{run_id}/trades
GET /backtests/runs/{run_id}/positions
GET /backtests/runs/{run_id}/orders
GET /backtests/runs/{run_id}/logs
GET /backtests/runs/{run_id}/download
```

普通研究员优先提交 Strategy Package V1 `weights` 包。`signals` 模式目前只是规范定义，
执行未实现；`code` 模式属于高级入口，生产应走 Docker 沙箱。

## Current Data Lake

服务器 `/ui/data` 在 2026-08-03 显示的主要覆盖：

| dataset | coverage | rows |
| --- | --- | ---: |
| `trading_calendar` | 2010-01-04 to 2026-07-31 | 4,025 |
| `instruments` | 1990-12-01 to 2026-07-02 | 5,554 |
| `prices_1d_pre` | 2010-01-04 to 2026-07-31 | 14,287,256 |
| `prices_1d_none` | 2010-01-04 to 2026-07-31 | 14,287,256 |
| `index_prices_1d` | 2010-01-04 to 2026-07-31 | 24,052 |
| `tradability_1d` | 2010-01-04 to 2026-07-31 | 14,362,695 |
| `valuation_1d` | 2010-01-04 to 2026-07-31 | 14,287,252 |
| `industry_classification` | 2010-01-04 to 2026-07-31 | 14,271,921 |
| `index_components` | 2010-01-04 to 2026-07-31 | 6,087,000 |
| `index_weights` | 2010-01-04 to 2026-07-31 | 6,077,000 |
| `risk_free_rate` | 2016-01-04 to 2026-07-14 | 2,632 |
| `financial_pit_field_pack` | 2016-04-08 to 2026-07-22 | 580,390 |
| `financial_cashflow_field_pack` | 2016-04-08 to 2026-07-23 | 580,404 |
| `financial_pit_quarterly` | 2015-01-15 to 2026-07-14 | 641,428 |
| `intraday_snapshots` | 2025-01-02 to 2025-08-29 | 5,078,067 |
| `cn_hxz_4_factors_monthly` | monthly derived | 121 |
| `cn_ff3_factors_monthly` | monthly derived | 121 |
| `hxz_monthly_research_panel` | monthly derived | 534,343 |

本地镜像会随同步进度变化。2026-08-03 本地通用查询层显示核心日频覆盖到
`2026-07-24`；服务器显示到 `2026-07-31`。

## Data Usage Policy

平台数据仅供内部学习、研究、回测、教学和策略验证使用。禁止外传原始行情数据、
接口返回数据、Parquet 文件、API token 或未脱敏的明细结果。详细制度见：

```text
docs/DATA_USAGE_POLICY.md
```

## Platform Audit

当前已经从“2025 MVP 验收”推进到“多研究员试运行”。平台现在能做：

- 通过 HTTP Data API 查询日频行情、估值、行业、指数成分/权重、财务 PIT、现金流 PIT、
  风险利率、日内快照和派生 HXZ/FF3 数据。
- 用本地 researcher template 或 handoff v0.4 生成标准权重包。
- 通过服务器统一回测引擎运行 long-only target weights 策略。
- 查看 current result、run history、独立 run_id 页面和 result zip。
- 管理 researcher token，按 researcher 记录 API/回测使用痕迹。
- 查看和调用 Factor Library MVP，生成内置因子的 target weights。
- 创建多模拟账户，上传目标权重，按日推进 paper trading。
- 用本地授权机器做 RQData 抓取、数据质量检查、每日更新和服务器同步。

当前限制：

- 回测引擎是自研 DailyBacktestEngine V0，不是完整交易所级撮合。
- 主推 `weights` 策略包；`signals` 执行未实现，`code` 模式不作为普通研究员默认入口。
- Data API 适合筛选和中等规模提取，不应当作无边界全市场下载服务。
- 财务和风险利率历史仍短于核心日频行情。
- 日内数据是固定快照，不是完整分钟线或实时行情。
- 研究员权限目前是 token 识别与审计，尚不是细粒度 RBAC。

VIX Q5 是真实验收样例，不是当前产品主线。它用于确认平台能力，不应继续把单一策略研究
当成平台建设主线。

## Next Improvements

优先改进顺序：

1. 数据产品化：把服务器 `/ui/data` 和 `/data/coverage` 作为唯一权威清单，自动生成
   `docs/COLLEAGUE_AGENT_SERVER_USAGE_REPORT_*.md`，减少手工过期。
2. 查询体验：增加 batch export job，支持大查询异步导出 CSV/Parquet result zip，而不是让
   研究员分页拉全市场。
3. 回测可信度：补充 benchmark 对齐、停牌/涨跌停/交易成本/换手约束的可解释报告，并对
   `DailyBacktestEngine V0` 做更多边界测试。
4. Handoff 稳定化：把 `handoff/researcher_onboarding_v0.4.zip` 纳入自动构建和 validator
   smoke，防止字段名再次漂移。
5. 数据补齐：优先补 `risk_free_rate` 到 2010，评估财务 PIT/现金流 PIT 能否扩展到 2010；
   分钟级只保留明确需要的快照点。
6. 运维自动化：每日更新、质量审计、server sync、API smoke 和 backtest smoke 组成一条
   可重复的 release checklist。
7. 权限治理：token rotation、禁用/启用、使用量报告已经有基础，下一步做按 researcher 的
   dashboard、限流和敏感下载告警。

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

当前正式核心日频支持区间：

```text
SUPPORTED_DATE_RANGE=2010-01-04 to latest complete data lake trading date
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
