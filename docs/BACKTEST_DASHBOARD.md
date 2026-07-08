# Backtest Dashboard

V0 dashboard 是 FastAPI + Jinja2 服务端渲染页面，用来查看当前 current 回测结果。
它不调用 RQData，不运行回测，只读取 `CurrentBacktestStore` 中的标准结果文件。

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

## 下载

页面左侧提供“下载结果包”按钮，链接到：

```text
/backtests/current/download
```

如果当前没有回测结果，页面会显示空状态，下载按钮不可用。

## V0 限制

1. 单用户 current。
2. 不做登录系统。
3. 不做历史回测横向对比。
4. 不做复杂前端构建。
5. 生产权限模型后续再补。

后续计划：横向对比、本地 result viewer、多用户 current。
