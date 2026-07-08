# Backtest Sandbox

## 为什么必须使用 Docker

研究员策略代码不能直接在宿主机运行。策略可能包含死循环、大量内存分配、
文件误写、网络访问或依赖污染。Docker 沙箱用于把策略运行限制在可控边界内。

## V0 资源限制

Docker 命令骨架会包含：

```text
CPU limit
memory limit
pids limit
timeout
no network
read-only data mount
read-only container filesystem
tmpfs /tmp
no .env mount
```

数据目录以只读方式挂载：

```text
<data_dir>:/app/data/rqdata:ro
```

结果目录以可写方式挂载：

```text
<run_dir>:/app/runs/backtests/<run_id>:rw
```

## 当前边界

V0 已提供 `run_backtest_in_docker(...)`，通过 `subprocess.run` 执行 Docker
命令并捕获 stdout/stderr/timeout。pytest 不依赖本机 Docker，因此测试只覆盖命令构造
和返回结构。

本地开发可以直接运行 Worker CLI；真实生产应通过 Docker 沙箱运行用户策略。
API job 默认使用 `BACKTEST_EXECUTION_MODE=local` 方便开发，生产环境必须改为
`BACKTEST_EXECUTION_MODE=docker`。

Strategy Package 的 code 模式同样必须在生产环境走 Docker。weights 模式不执行用户代码，
只读取标准化权重文件并进入平台统一回测引擎。

## 后续接入

Worker CLI：

```text
python -m rq_platform.backtest.worker --config /app/config/config.json --strategy /app/strategy/strategy.py --output-root /app/runs/backtests
```

`worker.py` 负责读取 run 配置、加载只读数据、执行策略、写出标准结果包。
失败时写出 `error.json` 和 `logs.txt`，并返回非 0 exit code。
