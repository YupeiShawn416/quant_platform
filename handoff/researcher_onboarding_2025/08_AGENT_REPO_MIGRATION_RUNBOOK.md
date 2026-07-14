# 用 Agent 标准化旧策略并提交服务器回测

## 0. 你需要准备的全部东西

开始前只需要准备这些：

- 原策略代码仓库路径
- onboarding 文件夹路径
- agent 输出项目路径
- `SERVER_URL`
- `API_TOKEN`
- `SUPPORTED_DATE_RANGE=2016-01-04 to 2026-07-10`
- `STRATEGY_NAME`
- `RUN_ID`
- `BACKTEST_START_DATE`
- `BACKTEST_END_DATE`
- `INITIAL_CASH`
- `BENCHMARK`
- 最终要提交的文件

`API_TOKEN` 由管理员单独发给你。每位研究员使用自己的独立 token，平台会自动记录每次回测是谁提交的。

最终要提交：

- `strategy_package.zip`
- result zip
- `run_id`
- 简短研究说明

复制下面这段，填好尖括号里的内容：

```text
ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 Agent 输出标准化项目的路径>

SERVER_URL=<管理员提供>
API_TOKEN=<管理员提供>
SUPPORTED_DATE_RANGE=2016-01-04 to 2026-07-10

STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id，例如 my_strategy_2016_2026_v1>
BACKTEST_START_DATE=<必须在 supported range 内> 格式如 2025-01-02
BACKTEST_END_DATE=<必须在 supported range 内>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG
```

## 1. 最短操作流程

1. 填好第 0 节的信息块。
2. 把信息块和第 2 节任务一起复制给 Agent。
3. Agent 读取旧策略仓库，把策略转成标准 `strategy_package.zip`。
4. Agent 上传服务器并提交回测。
5. 保存 `run_id`。
6. 打开 `$SERVER_URL/ui/backtests/runs/<RUN_ID>` 查看结果。
7. 下载 result zip，并提交 `strategy_package.zip`、result zip 和简短研究说明。

`current` 页面只是最近一次回测，会被最新回测覆盖。自己的结果请优先保存 `run_id`，并查看 `/ui/backtests/runs/<run_id>`。
回测提交后，平台会自动记录提交人，不需要你手动填写 researcher_id。

如果你只想做模拟盘跟踪，可以让 agent 生成 `target_weights.csv`，由管理员创建 paper account 后上传到 `/paper/accounts/<paper_id>/target-weights`，再打开 `SERVER_URL/ui/paper/<paper_id>` 查看 NAV、持仓、订单和成交。

如果旧策略需要平台标准数据，可以让 Agent 使用
`examples/researcher_api_usage/quant_platform_client.py`，通过你的 `API_TOKEN`
按日期和证券代码分页拉取数据。

## 2. 直接复制给 Agent 的任务

把第 0 节信息块填好后，连同下面这段一起发给 Agent：

```text
你现在帮我把一个旧量化策略仓库迁移成 Quant Platform 可回测的标准 strategy package，并提交服务器回测。

【我填写好的信息】

ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 Agent 输出标准化项目的路径>

SERVER_URL=<管理员提供>
API_TOKEN=<管理员提供>
SUPPORTED_DATE_RANGE=2016-01-04 to 2026-07-10

STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id，例如 my_strategy_2016_2026_v1>
BACKTEST_START_DATE=<必须在 supported range 内>
BACKTEST_END_DATE=<必须在 supported range 内>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG

【请你完成】

1. 读取 ORIGINAL_STRATEGY_REPO，找出策略逻辑、数据需求、调仓频率和权重输出方式。
2. 不要修改原策略仓库。
3. 在 WORK_PROJECT_DIR 新建标准化项目。
4. 生成符合平台要求的 strategy_package.zip。
5. 回测区间必须在 SUPPORTED_DATE_RANGE 内。
6. 上传到 SERVER_URL，并提交回测。
7. 输出 run_id、summary、Dashboard 链接和 result zip 下载方式。
8. 如果旧策略无法迁移，请说明原因，并给出最小改造方案。

【迁移要求】

请优先迁移成日频目标权重格式：

trade_date, order_book_id, weight

要求：

1. trade_date 是 YYYY-MM-DD。
2. order_book_id 是平台证券代码，例如 000001.XSHE、600519.XSHG。
3. weight 是非负数字。
4. 同一天同一证券不能重复。
5. 每天 weight 总和不能超过 1.0。

【不要做】

不要访问 SSH。
不要访问 RQData。
不要登录服务器。
不要修改平台代码。
不要读取 .env、私钥、密码、真实账户文件。
不要打印 API_TOKEN。
不要把 API_TOKEN 写进代码、配置、日志、README 或 zip。

【完成后请用中文输出】

1. 旧策略逻辑摘要。
2. 修改了哪些文件。
3. 回测区间。
4. strategy_package.zip 路径。
5. 上传服务器是否成功。
6. run_id。
7. summary。
8. Dashboard 链接：SERVER_URL/ui/backtests/runs/RUN_ID
9. result zip 下载方式。
10. 无法迁移或需要人工确认的地方。
```

## 3. Agent 需要跑的命令

Agent 应该在标准化项目目录里执行：

```bash
cd "$WORK_PROJECT_DIR"

export QUANT_PLATFORM_API_URL="$SERVER_URL"
export QUANT_PLATFORM_API_TOKEN="$API_TOKEN"

python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py
```

完成后让 Agent 输出：

```text
RUN_ID=<实际 run_id>
RUN_DASHBOARD_URL=$SERVER_URL/ui/backtests/runs/<RUN_ID>
RESULT_ZIP=<下载到的 result zip 路径>
STRATEGY_PACKAGE=<strategy_package.zip 路径>
```

## 4. 怎么看结果

主要入口：

```text
$SERVER_URL/ui/backtests/runs/<RUN_ID>
```

历史列表：

```text
$SERVER_URL/ui/backtests/runs
```

最近一次结果：

```text
$SERVER_URL/ui/backtests/current
```

`current` 会被最新回测覆盖，不要把 `current` 当成长期结果保存。

最终请保存：

- `run_id`
- result zip
- `strategy_package.zip`
- 简短研究说明

## 5. 当前平台支持什么

支持：

- 日频 A 股策略
- weights package
- long-only / 权重型策略
- run_id 独立结果
- result zip 下载
- `2016-01-04 to 2026-07-10` 的基础日频数据

暂不支持或不要承诺：

- 实时行情
- 分钟级 / tick 级
- 服务器训练机器学习模型
- 自动 paper trading
- 研究员直接 SSH
- 研究员直接使用 RQData license

机器学习策略的准确说法：

平台不负责训练模型，但可以回测你在本地生成的标准目标权重。

## 6. 如果原策略迁移不了

常见原因：

- 策略依赖外部私有数据
- 策略只输出交易信号，不输出目标权重
- 策略频率不是日频
- 策略用了分钟级数据
- 策略有未来函数
- 策略没有明确回测区间

处理方式：

- 先改成日频目标权重
- 先跑 supported date range 内的小区间
- 先只迁移核心逻辑，不迁移所有花哨功能

## 7. 常见问题

Q: 为什么我不看 current？

A: `current` 是最近一次回测，别人跑了会变。请保存 `run_id`，看 `/ui/backtests/runs/<run_id>`。

Q: 数据区间是什么？

A: 当前 supported range 是 `2016-01-04 to 2026-07-10`。后续由管理员通过 daily update 扩展。

Q: 我需要服务器密码吗？

A: 不需要。

Q: 我需要 RQData license 或 `.env` 吗？

A: 不需要。

Q: 我应该交 current 页面截图吗？

A: 不建议只交截图。请提交 `run_id`、result zip、`strategy_package.zip` 和简短研究说明。
