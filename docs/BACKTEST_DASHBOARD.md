# Backtest Dashboard

Dashboard 是 FastAPI + Jinja2 服务端渲染页面，用来查看 backtest result bundle。
它不运行回测，只读取平台已经生成的标准结果文件。

Dashboard 是平台统一结果展示层。研究员可以在本地生成 Strategy Package，但最终应以
Dashboard 和 result zip 中的平台结果作为回测结论来源。

## 启动

```bash
make api
```

先生成 current：

```bash
make backtest-api-smoke
```

打开：

```text
http://127.0.0.1:8000/ui/backtests/current
```

历史 run 列表：

```text
http://127.0.0.1:8000/ui/backtests/runs
```

按 run_id 查看：

```text
http://127.0.0.1:8000/ui/backtests/runs/{run_id}
```

## 页面模块

```text
概览
净值曲线
账户
持仓
交易日志
订单
日志
```

概览页展示核心绩效指标。净值页使用本地静态 JS 画 SVG 折线图，不依赖 CDN。
账户默认显示最近 100 行，交易和订单默认显示最近 200 行，日志显示最后 500 行。

如果当前结果包的 `benchmark_fallback_used=true`，概览页和净值页会显示醒目的
benchmark warning。概览页会把基准收益、超额收益、跟踪误差和信息比率等指标
标记为 `N/A / unreliable`，避免把 fallback 直线误读成真实基准。

当 `index_prices_1d` 已包含配置的 benchmark，例如 `000300.XSHG`，回测结果会使用
真实指数 `close` 生成 `benchmark_nav`。此时 Dashboard 不显示 fallback warning，
基准曲线不再是固定 `1.0` 直线。

## 下载

页面左侧提供“下载结果包”按钮，链接到：

```text
/backtests/current/download
```

如果当前没有回测结果，页面会显示空状态，下载按钮不可用。

`current` 只代表最新结果。新回测可能覆盖 current。

Stage 24 起，每次回测会生成独立 `run_id`，可以在 `/ui/backtests/runs` 列表中查看。
研究员应保存自己的 run_id，并优先使用 `/ui/backtests/runs/{run_id}` 查看结果。
需要长期保存时仍必须下载 result zip。

## V0 限制

1. current 仍是单用户最新结果。
2. 不做登录系统。
3. 不做多用户隔离。
4. 不做复杂前端构建。
5. 生产权限模型后续再补。
6. cached result 会过期。
7. 不支持多策略横向对比。

后续计划：横向对比、本地 result viewer、多用户隔离。

## Acceptance Use

2025 MVP 验收时至少检查：

- overview 可打开
- nav 可打开
- account 可打开
- positions 可打开
- trades 可打开
- orders 可打开
- logs 可打开
- result zip 可下载
- benchmark 缺失时显示 warning
- runs 列表可打开
- run_id detail 可打开
