# 用 Agent 标准化旧策略并提交服务器回测

这份文档给完全不懂服务器的量化研究员使用。

你只需要把本文档里的占位符改成自己的信息，然后把这份文档、你的原策略代码仓库、
以及 onboarding 文件夹路径一起提供给 agent。agent 应该能完成策略迁移、生成标准
`strategy_package.zip`、上传服务器回测、下载 result zip。你最后用浏览器打开 Dashboard
即可查看结果。

## 1. 你要准备什么

你需要准备三样东西：

```text
1. 你的原策略代码仓库
2. Quant Platform researcher onboarding 文件夹
3. 管理员给你的服务器访问信息
```

不要把 API token、`.env`、私钥、真实账户信息发到公开 AI 工具、公开仓库或群聊。

## 2. 当前平台能力

当前平台支持的官方回测方式：

```text
weights package
```

也就是说，平台最终需要的是每日目标权重：

```text
trade_date, order_book_id, weight
```

当前平台不要求研究员上传完整 Python 回测脚本，也不要求研究员懂服务器部署。

## 3. 当前可回测时间范围

当前 MVP 数据范围：

```text
2025-01-02 到 2025-12-31
```

推荐先跑短区间 smoke test：

```text
2025-01-02 到 2025-02-28
```

短区间跑通后，再扩展到全年：

```text
2025-01-02 到 2025-12-31
```

如果你的原策略需要 2025 以前的数据做长回看窗口，当前 MVP 可能无法完整支持，需要先报告
给管理员，不要让 agent 自己去抓外部数据。

## 4. 研究员需要填写的信息

把下面这段复制一份，并替换尖括号里的内容：

```text
ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 agent 输出标准化项目的路径>

SERVER_URL=<管理员提供的服务器地址，例如 https://example.com>
API_TOKEN=<管理员单独提供的 token，不要提交到 Git>
DASHBOARD_URL=<SERVER_URL>/ui/backtests/current

BACKTEST_START_DATE=2025-01-02
BACKTEST_END_DATE=2025-02-28

STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id，例如 my_strategy_2025_smoke>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG
```

如果你使用的是公开或云端 AI agent，不要直接把真实 `API_TOKEN` 粘贴进去。更安全的做法是：

```bash
export QUANT_PLATFORM_API_URL="<SERVER_URL>"
export QUANT_PLATFORM_API_TOKEN="<API_TOKEN>"
```

然后告诉 agent 从环境变量读取，不要让 agent 把 token 写入任何文件。

## 5. 给 Agent 的完整任务

把下面整段复制给 agent。复制前，先把第 4 节里的占位符替换成你的实际信息。

```text
你现在要帮助我把一个旧量化策略仓库标准化成 Quant Platform 可回测的 weights package，
并通过服务器 API 提交回测。

一、输入信息

原策略代码仓库：
ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>

Quant Platform onboarding 文件夹：
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>

标准化项目输出目录：
WORK_PROJECT_DIR=<希望输出标准化项目的路径>

服务器地址：
SERVER_URL=<管理员提供的服务器地址>

API token：
从环境变量 QUANT_PLATFORM_API_TOKEN 读取。不要把 token 写入任何文件，不要打印 token。

Dashboard：
DASHBOARD_URL=<SERVER_URL>/ui/backtests/current

回测区间：
BACKTEST_START_DATE=2025-01-02
BACKTEST_END_DATE=2025-02-28

策略信息：
STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG

二、目标

请阅读 ORIGINAL_STRATEGY_REPO 中的策略逻辑，并把它迁移到 ONBOARDING_DIR 里的
sample_strategy_project 标准结构中。迁移后，项目必须能够：

1. 从平台 API 读取 2025 MVP 数据。
2. 计算原策略对应的因子或信号。
3. 生成标准每日目标权重。
4. 校验 weights 格式。
5. 构建 strategy_package.zip。
6. 上传到服务器 /backtests/run-package。
7. 下载 result zip。
8. 输出浏览器 Dashboard 地址。

三、必须遵守的限制

1. 不要修改原策略仓库。
2. 不要修改 Quant Platform 平台源码。
3. 不要调用 RQData。
4. 不要抓外部数据。
5. 不要读取 .env、私钥、密码、真实账户文件。
6. 不要打印 API token。
7. 不要把 API token 写入代码、配置、日志、README 或 zip。
8. 不要提交或外传原始行情数据、API 返回数据、parquet、csv、result zip。
9. 不要自己写回测引擎。
10. 不要绕过 package 校验。
11. 当前只使用 2025-01-02 到 2025-12-31 范围内的数据。

四、你需要重点阅读的文件

请先阅读：

1. ONBOARDING_DIR/00_READ_ME_FIRST.md
2. ONBOARDING_DIR/01_DATA_USAGE_RULES.md
3. ONBOARDING_DIR/02_SIMPLE_USER_MANUAL.md
4. ONBOARDING_DIR/04_SUBMISSION_REQUIREMENTS.md
5. ONBOARDING_DIR/05_TROUBLESHOOTING.md
6. ONBOARDING_DIR/sample_strategy_project/README.md
7. ONBOARDING_DIR/sample_strategy_project/configs/strategy.yaml
8. ONBOARDING_DIR/sample_strategy_project/scripts/
9. ONBOARDING_DIR/sample_strategy_project/src/strategy_research/

然后阅读 ORIGINAL_STRATEGY_REPO，识别：

1. universe 定义
2. 数据字段依赖
3. 因子计算逻辑
4. 信号方向，是越大越好还是越小越好
5. 调仓频率
6. 持仓数量或权重规则
7. 停牌、涨跌停、ST、上市天数等过滤规则
8. 是否需要行业、市值、指数成分、估值等辅助数据

五、迁移方式

请复制 ONBOARDING_DIR/sample_strategy_project 到 WORK_PROJECT_DIR。

主要只允许修改这些文件：

1. WORK_PROJECT_DIR/configs/strategy.yaml
2. WORK_PROJECT_DIR/src/strategy_research/factor.py
3. WORK_PROJECT_DIR/src/strategy_research/signal.py
4. WORK_PROJECT_DIR/src/strategy_research/portfolio.py

必要时可以小幅修改：

1. WORK_PROJECT_DIR/scripts/01_load_data.py
2. WORK_PROJECT_DIR/scripts/02_compute_factor.py
3. WORK_PROJECT_DIR/scripts/03_generate_signal.py
4. WORK_PROJECT_DIR/scripts/04_generate_weights.py

但不要改变最终标准输出格式。

六、标准输出格式

最终 weights 文件必须包含：

trade_date, order_book_id, weight

要求：

1. trade_date 是 YYYY-MM-DD。
2. order_book_id 是平台证券代码，例如 000001.XSHE、600519.XSHG。
3. weight 是非负数字。
4. 同一天同一证券不能重复。
5. 每天 weight 总和不能超过 1.0。
6. long-only 策略不能出现负权重。

七、运行步骤

请在 WORK_PROJECT_DIR 中依次运行：

python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py

如果某一步失败：

1. 先阅读错误信息。
2. 修复标准化项目中的策略逻辑或字段映射。
3. 不要绕过校验。
4. 不要修改服务器。
5. 不要尝试抓外部数据补缺口。

八、完成后请输出

请最终用中文输出：

1. 你从原策略仓库识别出的策略逻辑摘要。
2. 你修改了哪些文件。
3. 使用的回测区间。
4. 生成的 strategy_package.zip 路径。
5. 上传服务器是否成功。
6. result zip 下载路径。
7. summary 中的 total_return、sharpe、max_drawdown、benchmark_return、excess_return。
8. benchmark_missing、benchmark_fallback_used、benchmark_metrics_reliable 是否可靠。
9. 浏览器 Dashboard 地址：DASHBOARD_URL。
10. 如果有无法迁移的原策略逻辑，请明确列出。
```

## 6. 研究员本地要运行的命令

如果 agent 已经在你的电脑或同一个开发环境里，可以让 agent 运行。你也可以自己运行：

```bash
cd <WORK_PROJECT_DIR>

export QUANT_PLATFORM_API_URL="<SERVER_URL>"
export QUANT_PLATFORM_API_TOKEN="<API_TOKEN>"

python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py
```

Windows PowerShell：

```powershell
cd <WORK_PROJECT_DIR>

$env:QUANT_PLATFORM_API_URL="<SERVER_URL>"
$env:QUANT_PLATFORM_API_TOKEN="<API_TOKEN>"

python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py
```

## 7. 浏览器查看 Dashboard

提交成功后，打开浏览器访问：

```text
<SERVER_URL>/ui/backtests/current
```

注意：当前 MVP 只保留一个 `current` 回测结果。新回测会覆盖旧 current。

所以你跑完之后要立刻下载 result zip：

```text
<SERVER_URL>/backtests/current/download
```

或使用脚本下载到：

```text
<WORK_PROJECT_DIR>/data/output/result.zip
```

## 8. 管理员需要给研究员什么

管理员至少需要提供：

```text
SERVER_URL=<服务器地址>
DASHBOARD_URL=<SERVER_URL>/ui/backtests/current
API_TOKEN=<通过安全渠道单独发送>
SUPPORTED_DATE_RANGE=2025-01-02 to 2025-12-31
ONBOARDING_DIR=<研究员本地 handoff/researcher_onboarding_2025 路径>
```

管理员不要把真实 token 写入 Git、Markdown 文件、截图、群公告或公开 agent prompt。

## 9. 管理员发给研究员的消息模板

```text
你好，这是 Quant Platform 研究员试运行信息。

请使用 handoff/researcher_onboarding_2025/08_AGENT_REPO_MIGRATION_RUNBOOK.md。

服务器地址：
<SERVER_URL>

Dashboard：
<SERVER_URL>/ui/backtests/current

当前可回测时间范围：
2025-01-02 到 2025-12-31

API token：
我会通过安全渠道单独发给你。不要写入代码、Git、Markdown 或公开 AI 工具。

你的任务：
把你的原策略仓库和 onboarding 文件夹一起交给 agent，让 agent 按 runbook 把策略迁移成
weights package，上传服务器回测，然后用浏览器打开 Dashboard 查看结果。
```

## 10. 常见问题

### Agent 读不懂原策略怎么办？

让 agent 先输出“策略逻辑摘要”，不要急着改代码。你确认摘要正确后，再让它迁移。

### 原策略依赖 2025 以前历史窗口怎么办？

当前 MVP 只有 2025 数据。请把缺失依赖列出来交给管理员，不要让 agent 自己抓外部数据。

### Dashboard 看不到我的结果怎么办？

先确认 `scripts/07_submit_package.py` 是否返回成功。如果别人上传了新回测，你的 current 可能
被覆盖，需要重新提交一次 package。

### 可以把 result zip 发给别人吗？

只能按内部规则提交给管理员。不要公开外传，因为里面包含明细回测结果。
