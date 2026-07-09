# 用 Agent 标准化旧策略并提交服务器回测

这是一份给研究员直接使用的 agent 操作 runbook。

你只需要准备好下面的信息，把第 2 节整段复制给 agent。agent 完成后，你用浏览器打开
Dashboard 看结果，并下载 result zip 保存。

## 0. 你需要准备的全部东西

开始前，请准备好：

- 原策略代码仓库路径
- onboarding 文件夹路径
- agent 输出项目路径
- 服务器地址
- API token
- Dashboard 地址
- 回测开始日期
- 回测结束日期
- 策略名称
- run_id
- 初始资金
- benchmark
- 最终要提交的文件

最终要提交的文件通常是：

- `strategy_package.zip`
- 平台下载的 result zip
- 简短研究说明
- 遇到的问题说明

把下面这段复制一份，并替换尖括号里的内容：

```text
ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 agent 输出标准化项目的路径>

SERVER_URL=<管理员提供的服务器地址>
API_TOKEN=<管理员单独提供的 token>
DASHBOARD_URL=<SERVER_URL>/ui/backtests/current

BACKTEST_START_DATE=2025-01-02
BACKTEST_END_DATE=2025-02-28

STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id，例如 my_strategy_2025_smoke>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG
```

当前可回测范围：

```text
2025-01-02 到 2025-12-31
```

建议第一次先用：

```text
2025-01-02 到 2025-02-28
```

跑通后再改成全年。

## 1. 你要填写哪些信息

最少需要填写这些字段：

```text
ORIGINAL_STRATEGY_REPO
ONBOARDING_DIR
WORK_PROJECT_DIR
SERVER_URL
API_TOKEN
DASHBOARD_URL
BACKTEST_START_DATE
BACKTEST_END_DATE
STRATEGY_NAME
RUN_ID
INITIAL_CASH
BENCHMARK
```

填写建议：

- `ORIGINAL_STRATEGY_REPO`：你的旧策略仓库路径。
- `ONBOARDING_DIR`：本文件所在的 `handoff/researcher_onboarding_2025` 路径。
- `WORK_PROJECT_DIR`：让 agent 生成标准化项目的新路径，不要直接覆盖旧策略仓库。
- `SERVER_URL`：管理员给你的服务器地址。
- `API_TOKEN`：管理员单独给你的 token。
- `DASHBOARD_URL`：一般是 `<SERVER_URL>/ui/backtests/current`。
- `RUN_ID`：建议只用英文、数字、下划线，例如 `my_strategy_2025_smoke`。

## 2. 复制这一整段给 agent

先把第 0 节的信息块填好，再把下面整段复制给 agent。

```text
你现在要帮我把一个旧量化策略仓库标准化成 Quant Platform 可回测的 weights package，
并提交到服务器回测。

【我已经填写好的信息】

ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 agent 输出标准化项目的路径>

SERVER_URL=<管理员提供的服务器地址>
API_TOKEN=<管理员单独提供的 token>
DASHBOARD_URL=<SERVER_URL>/ui/backtests/current

BACKTEST_START_DATE=2025-01-02
BACKTEST_END_DATE=2025-02-28

STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id，例如 my_strategy_2025_smoke>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG

【你的目标】

请阅读 ORIGINAL_STRATEGY_REPO 中的旧策略逻辑，把它迁移成 ONBOARDING_DIR 里的标准
sample_strategy_project 形式，并在 WORK_PROJECT_DIR 输出新项目。

最终必须生成：

1. strategy_package.zip
2. 平台 result zip
3. 回测 summary
4. Dashboard 地址

【你需要先读的 onboarding 文件】

1. ONBOARDING_DIR/00_READ_ME_FIRST.md
2. ONBOARDING_DIR/02_SIMPLE_USER_MANUAL.md
3. ONBOARDING_DIR/04_SUBMISSION_REQUIREMENTS.md
4. ONBOARDING_DIR/05_TROUBLESHOOTING.md
5. ONBOARDING_DIR/sample_strategy_project/README.md
6. ONBOARDING_DIR/sample_strategy_project/configs/strategy.yaml
7. ONBOARDING_DIR/sample_strategy_project/scripts/
8. ONBOARDING_DIR/sample_strategy_project/src/strategy_research/

【你需要从旧策略仓库识别什么】

1. 股票池
2. 因子逻辑
3. 信号方向，是越大越好还是越小越好
4. 调仓频率
5. 持仓数量
6. 权重生成规则
7. 需要用到哪些数据字段
8. 哪些逻辑无法在当前 2025 数据范围内完整复现

【迁移要求】

请复制 ONBOARDING_DIR/sample_strategy_project 到 WORK_PROJECT_DIR。

优先只修改这些文件：

1. WORK_PROJECT_DIR/configs/strategy.yaml
2. WORK_PROJECT_DIR/src/strategy_research/factor.py
3. WORK_PROJECT_DIR/src/strategy_research/signal.py
4. WORK_PROJECT_DIR/src/strategy_research/portfolio.py

最终权重文件必须包含：

trade_date, order_book_id, weight

要求：

1. trade_date 是 YYYY-MM-DD。
2. order_book_id 是平台证券代码，例如 000001.XSHE、600519.XSHG。
3. weight 是非负数字。
4. 同一天同一证券不能重复。
5. 每天 weight 总和不能超过 1.0。

【请依次运行】

cd WORK_PROJECT_DIR

export QUANT_PLATFORM_API_URL="<SERVER_URL>"
export QUANT_PLATFORM_API_TOKEN="<API_TOKEN>"

python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py

【如果失败】

不要改服务器，不要绕过校验，不要抓外部数据。
请先修复 WORK_PROJECT_DIR 中的策略逻辑、字段映射或权重格式。

【完成后请用中文输出】

1. 旧策略逻辑摘要。
2. 修改了哪些文件。
3. 回测区间。
4. strategy_package.zip 路径。
5. 上传服务器是否成功。
6. result zip 路径。
7. total_return、sharpe、max_drawdown、benchmark_return、excess_return。
8. benchmark_missing、benchmark_fallback_used、benchmark_metrics_reliable。
9. Dashboard 地址。
10. 无法迁移或需要人工确认的地方。

【安全要求】

不要修改原策略仓库。
不要读取 .env、私钥、密码、真实账户文件。
不要打印 API_TOKEN。
不要把 API_TOKEN 写进代码、配置、日志、README 或 zip。
不要提交或外传原始数据、平台返回数据、结果明细或 result zip。
```

## 3. Agent 跑完后你要检查什么

Agent 跑完后，你只需要检查这些结果：

- 是否生成了 `strategy_package.zip`
- 是否上传服务器成功
- 是否下载了 result zip
- 是否输出了 summary
- 是否输出了 Dashboard 地址
- 是否说明了不能迁移的旧策略逻辑

如果 agent 说某一步失败，先把错误信息发给管理员或让 agent 根据
`05_TROUBLESHOOTING.md` 修复，不要自己猜。

## 4. 你最后要交什么

请提交：

- `strategy_package.zip`
- result zip
- 简短研究说明
- agent 输出的策略逻辑摘要
- agent 提到的无法迁移问题

不要提交：

- API token
- `.env`
- 私钥或密码
- 原始数据文件
- 平台返回的明细数据
- 不该公开的回测明细

## 5. 怎么打开 Dashboard 看结果

上传成功后，用浏览器打开：

```text
<SERVER_URL>/ui/backtests/current
```

也就是你填写的：

```text
DASHBOARD_URL=<SERVER_URL>/ui/backtests/current
```

注意：当前只保留一个 `current` 结果。别人提交新回测后，你的 current 可能会被覆盖。

所以你看到结果后，请立刻下载 result zip 保存。

## 6. 管理员应该发给研究员什么

管理员可以直接发：

```text
你好，这是 Quant Platform 研究员试运行信息。

请使用：
handoff/researcher_onboarding_2025/08_AGENT_REPO_MIGRATION_RUNBOOK.md

服务器地址：
<SERVER_URL>

Dashboard：
<SERVER_URL>/ui/backtests/current

当前可回测时间范围：
2025-01-02 到 2025-12-31

建议首次回测区间：
2025-01-02 到 2025-02-28

API token：
我会通过安全渠道单独发给你。

你需要提供：
1. 你的原策略代码仓库路径
2. onboarding 文件夹路径
3. 希望 agent 输出标准化项目的路径
4. 策略名称和 run_id

完成后请提交 strategy_package.zip、result zip 和简短研究说明。
```

## 7. 简短提醒

- 第一次先跑短区间，跑通后再跑全年。
- 不要让 agent 覆盖你的原策略仓库。
- 不要把 token 写进任何文件。
- 不要把数据、结果明细、result zip 发到公开平台。
- 如果旧策略依赖 2025 以前的数据，先记录问题并交给管理员确认。
