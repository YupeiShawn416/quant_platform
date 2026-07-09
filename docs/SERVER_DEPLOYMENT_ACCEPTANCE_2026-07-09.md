# Server Deployment Acceptance Record - 2026-07-09

## 1. Acceptance Summary

2025 data version Quant Platform MVP has completed server deployment acceptance.
Public API access, token authentication, Strategy Package upload, server-side
backtest execution, Dashboard display, and result zip download all passed.

This record contains no real API token, private key, server credential, or `.env`
content.

## 2. Deployment Scope

- Data scope: 2025 MVP data.
- Supported researcher entry path: Strategy Package `weights` mode.
- Server role: API, Dashboard, backtest judge, result zip download.
- Researcher scripts: run locally on a researcher's machine, notebook, or AI
  agent project.
- RQData: server does not directly access RQData by default.

Core principle:

```text
因子可以自由研究，回测必须统一裁判。
```

## 3. Verified Checks

- [x] `/health` passed.
- [x] `/status` passed.
- [x] `create-demo-weights-package` passed.
- [x] `submit-demo-weights-package` passed through public API.
- [x] `/backtests/current/summary` passed.
- [x] `/backtests/current/download` passed.
- [x] Dashboard current result displayed.
- [x] Result zip includes expected files.
- [x] `benchmark_missing=false`.
- [x] `benchmark_metrics_reliable=true`.

## 4. Demo Backtest Summary

| Field | Value |
|---|---:|
| run_id | `demo_weights_package` |
| strategy_name | `Demo Weights Q5 Long Only` |
| start_date | `2025-01-02` |
| end_date | `2025-02-28` |
| initial_cash | `1000000` |
| final_value | `1000503.2201908961` |
| total_return | `0.0008563602874829268` |
| annual_return | `0.0061821868260196755` |
| annual_volatility | `0.12548519705783817` |
| sharpe | `0.04926626383803824` |
| max_drawdown | `-0.026192642226284923` |
| benchmark | `000300.XSHG` |
| benchmark_return | `0.018232014321450274` |
| excess_return | `-0.017375654033967347` |
| tracking_error | `0.11948320896085446` |
| information_ratio | `-1.0540316464984008` |
| win_rate | `0.45714285714285713` |
| trade_count | `61` |
| nav count | `36` |
| trades count | `61` |

Benchmark status:

```text
benchmark_missing=false
benchmark_fallback_used=false
benchmark_metrics_reliable=true
```

## 5. Result Zip Contents

The downloaded result zip contained:

```text
current/backtest_result_demo_weights_package.zip
current/charts.json
current/config.json
current/daily_account.csv
current/logs.txt
current/manifest.json
current/monthly_returns.csv
current/nav.csv
current/orders.csv
current/positions.csv
current/rolling_metrics.csv
current/summary.csv
current/summary.json
current/trades.csv
```

## 6. Security Notes

- API token must not be committed or shared publicly.
- Token was required to be rotated after accidental exposure in chat.
- Researchers should receive token through a controlled channel only.
- Port 8000 should not be exposed publicly.
- Server should not directly access RQData unless authorization is confirmed.
- Researcher-facing files must use `<SERVER_URL>` and `<API_TOKEN>` placeholders.

## 7. Current Limitations

- Current-only result lifecycle.
- No run registry yet.
- No user management.
- No paper trading.
- Docker code mode is not production verified.
- Official training focuses on weights package only.
- 2025 data only for MVP trial.
- 2016-present data expansion is pending.

## 8. Next Step

Next step is to distribute the researcher onboarding pack and run a 1-3
researcher trial using 2025 data.
