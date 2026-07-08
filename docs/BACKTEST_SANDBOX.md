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

V0 只构造 Docker 命令，不真正执行 Docker，也不接入真实 RQAlpha。
用户脚本不允许直接在宿主机执行。

## 后续接入

真实回测引擎会接入：

```text
python -m rq_platform.backtest.worker --run-id <run_id>
```

`worker.py` 负责读取 run 配置、加载只读数据、执行策略、写出标准结果包。
