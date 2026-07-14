# 用 Agent 标准化旧策略并提交服务器回测

这份 runbook 给研究员使用。你不需要服务器密码、RQData license 或数据库账号。

## 0. 你需要准备的全部东西

- `SERVER_URL`：例如 `http://39.106.218.30`
- `API_TOKEN`：管理员单独发放给你
- Python 3.10 或 3.11
- 一个本地研究目录
  - Windows 示例：`C:\Users\<你的用户名>\quant_research`
  - Mac 示例：`~/quant_research`
- 原策略代码仓库路径
- onboarding 文件夹路径
- Agent 输出项目路径
- 策略名称、`run_id`、回测开始日期、回测结束日期、初始资金、benchmark
- 最终要提交的文件：`strategy_package.zip`、result zip、`run_id`、简短研究说明
- 可选工具：VS Code、Git、PowerShell、Python venv 或 conda

`API_TOKEN` 不要发到微信群、飞书群、GitHub 或聊天记录。如果泄露，联系管理员重置。

复制下面这段，填好尖括号里的内容：

```text
ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 Agent 输出标准化项目的路径>

SERVER_URL=http://39.106.218.30
API_TOKEN=<管理员单独提供>
SUPPORTED_DATE_RANGE=2016-01-04 to 2026-07-10

STRATEGY_NAME=<你的策略名称>
RUN_ID=<本次回测 run_id，例如 my_strategy_2016_2026_v1>
BACKTEST_START_DATE=<必须在 supported range 内，例如 2025-01-02>
BACKTEST_END_DATE=<必须在 supported range 内>
INITIAL_CASH=1000000
BENCHMARK=000300.XSHG
```

## 1. 先选择你的系统

后续大部分步骤完全相同，只有目录、虚拟环境和环境变量命令不同。

### Mac / Linux

使用 bash 或 zsh：

```bash
mkdir -p ~/quant_research
cd ~/quant_research

python3 -m venv .venv
source .venv/bin/activate

pip install pandas requests
```

设置平台地址和 token：

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="your_token_here"
```

测试：

```bash
curl "$QUANT_PLATFORM_API_URL/health"

curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/datasets"
```

Mac 不要照抄 Windows 的 `$env:`。

### Windows PowerShell

使用 PowerShell：

```powershell
mkdir C:\Users\$env:USERNAME\quant_research
cd C:\Users\$env:USERNAME\quant_research

python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

如果 PowerShell 禁止执行脚本，先运行：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

不要为了这一步随便用管理员权限修改全系统策略。

安装依赖：

```powershell
pip install pandas requests
```

设置平台地址和 token：

```powershell
$env:QUANT_PLATFORM_API_URL = "http://39.106.218.30"
$env:QUANT_PLATFORM_API_TOKEN = "your_token_here"
```

测试 health：

```powershell
Invoke-RestMethod "$env:QUANT_PLATFORM_API_URL/health"
```

或者：

```powershell
curl.exe "$env:QUANT_PLATFORM_API_URL/health"
```

测试 Data API：

```powershell
Invoke-RestMethod `
  -Headers @{ "X-API-Token" = $env:QUANT_PLATFORM_API_TOKEN } `
  "$env:QUANT_PLATFORM_API_URL/data/datasets"
```

PowerShell 里的 `curl` 可能是 alias，建议写 `curl.exe`。Windows 不要照抄 Mac 的 `export`。

## 2. 主线 1：查看平台页面

- 数据覆盖：http://39.106.218.30/ui/data
- 回测历史：http://39.106.218.30/ui/backtests/runs
- 研究员统计：http://39.106.218.30/ui/researchers
- 模拟盘：http://39.106.218.30/ui/paper
- Health：http://39.106.218.30/health

说明：

- `/ui/data` 看当前数据覆盖。
- `/ui/backtests/runs` 看历史回测。
- `/ui/researchers` 看研究员提交记录。
- `/ui/paper` 看模拟盘跟踪。

## 3. 主线 2：用 Data API 拉标准数据

研究员通过平台 Data API 拉数据：

- 不需要 RQData。
- 不需要服务器密码。
- 不需要数据库账号。
- 不要直接拿服务器文件。

建议把下面两个文件复制到你的本地研究目录：

```text
examples/researcher_api_usage/quant_platform_client.py
examples/researcher_api_usage/data_api_quickstart.py
```

安装最小依赖：

```bash
pip install pandas requests
```

Python 示例：

```python
import os

from quant_platform_client import QuantPlatformClient

client = QuantPlatformClient(
    os.environ["QUANT_PLATFORM_API_URL"],
    os.environ["QUANT_PLATFORM_API_TOKEN"],
)

print(client.list_datasets())
print(client.get_coverage())

df = client.query_dataset(
    "prices_1d_pre",
    start_date="2026-07-13",
    end_date="2026-07-13",
    order_book_ids="000001.XSHE",
    limit=100,
)
print(df.head())
```

Mac / Windows 都运行：

```bash
python data_api_quickstart.py
```

## 4. 主线 3：提交策略回测

最短流程：

1. 本地生成 `strategy_package.zip`。
2. 上传到 `/backtests/run-package`。
3. 平台返回 `run_id`。
4. 打开 `/ui/backtests/runs/<run_id>` 查看。
5. 下载 result zip。

必须记住：

- 回测结果以 `run_id` 为准。
- `current` 只是最近一次，会被别人或你的下一次回测覆盖。
- 如果要发给老板，发 `/ui/backtests/runs/<run_id>`。

## 5. 主线 4：进入 Paper Trading

当策略需要持续跟踪时，可以提交 `target_weights.csv` 到 paper trading。

CSV 格式：

```csv
trade_date,order_book_id,target_weight
2026-07-13,000001.XSHE,0.5
2026-07-13,000002.XSHE,0.5
```

说明：

- 第一版 paper trading 是模拟盘，不是实盘。
- 不接券商。
- 不会真实下单。
- 多个 paper account 可以并行存在。
- 老板可以在 `/ui/paper` 查看。
- 单个账户详情页是 `/ui/paper/<paper_id>`。

## 6. 直接复制给 Agent 的任务

把第 0 节信息块填好后，连同下面这段一起发给 Agent：

```text
你现在帮我把一个旧量化策略仓库迁移成 Quant Platform 可回测的标准 strategy package，并提交服务器回测。

【我填写好的信息】

ORIGINAL_STRATEGY_REPO=<你的原策略代码仓库本地路径>
ONBOARDING_DIR=<handoff/researcher_onboarding_2025 的本地路径>
WORK_PROJECT_DIR=<希望 Agent 输出标准化项目的路径>

SERVER_URL=http://39.106.218.30
API_TOKEN=<管理员单独提供>
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
4. 如需平台标准数据，只通过 Data API 拉取。
5. 生成符合平台要求的 strategy_package.zip。
6. 回测区间必须在 SUPPORTED_DATE_RANGE 内。
7. 上传到 SERVER_URL，并提交回测。
8. 输出 run_id、summary、Dashboard 链接和 result zip 下载方式。
9. 如果旧策略无法迁移，请说明原因，并给出最小改造方案。

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

不要登录服务器。
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

## 7. Agent 需要跑的命令

Agent 应该在标准化项目目录里执行。

Mac / Linux：

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

Windows PowerShell：

```powershell
cd $env:WORK_PROJECT_DIR

$env:QUANT_PLATFORM_API_URL = $env:SERVER_URL
$env:QUANT_PLATFORM_API_TOKEN = $env:API_TOKEN

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

## 8. 常见问题

Q: 401 Unauthorized 是什么？

A: token 没设置、token 写错、token 已被禁用、Windows 用了 `export`，或 Mac 用了 `$env:`。

Q: 403 Forbidden 是什么？

A: token 已禁用，或用了旧 token。联系管理员换新 token。

Q: 404 Not Found 是什么？

A: URL 或 endpoint 写错，或者服务器版本没有部署对应功能。

Q: 502 Bad Gateway 是什么？

A: 后端服务异常。联系管理员，不要自己修服务器。

Q: Windows PowerShell 里 curl 行为奇怪怎么办？

A: 使用 `curl.exe`，或使用 `Invoke-RestMethod`。

Q: 服务器是 https 吗？

A: 当前服务器是 `http`，不是 `https`。

Q: 为什么我不看 current？

A: `current` 是最近一次回测，别人跑了会变。请保存 `run_id`，看 `/ui/backtests/runs/<run_id>`。
