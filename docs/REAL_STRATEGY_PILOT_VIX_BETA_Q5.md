# Real Strategy Pilot: VIX Beta Q5 Long Only

## Paths

- Pilot project: `/Users/yupeishen/Desktop/vix_beta_q5_long_only_pilot`
- Original project: `/Users/yupeishen/Desktop/rq_vix_beta_cross_section`
- Original script: `/Users/yupeishen/Desktop/rq_vix_beta_cross_section/experiments/02_vix_beta_cross_section/scripts/08_backtest_vix_beta_portfolios.py`
- Score panel: `/Users/yupeishen/Desktop/rq_vix_beta_cross_section/experiments/02_vix_beta_cross_section/data/processed/vix_beta_score_panel.parquet`
- Strategy package: `/tmp/vix_beta_q5_long_only_package.zip`

## Strategy

- Mode: Strategy Package V1 `weights`
- Logic: `Q5LongOnly`
- Score column: `score_negative_vix_beta`
- Universe filters: `in_csi300 == True`, `is_tradable == True`
- Portfolio construction: daily rank, `pd.qcut(..., q=5, duplicates="drop") + 1`, bucket 5, equal-weight long-only
- Run window: `2025-01-02` to `2025-12-31`

## Generated Outputs

The pilot project generated:

- `data/output/market_data.csv`
- `data/output/factor.csv`
- `data/output/signal.csv`
- `data/output/weights.csv`
- `data/output/weights.parquet`
- `data/output/validation_report.md`
- `/tmp/vix_beta_q5_long_only_package.zip`

Weights summary:

- Weight date range: `2025-01-02` to `2025-12-31`
- Trading dates: `243`
- Weight rows: `14580`
- Average holdings per day: `60.00`
- Max daily weight sum: `1.000000`

## Platform Submission

`POST /backtests/run-package` succeeded.

Current summary:

```text
run_id: vix_beta_q5_long_only_2025
strategy_name: VIX Beta Q5 Long Only
total_return: 0.4095660855105021
annual_return: 0.4297035561737874
sharpe: 2.838860546964993
max_drawdown: -0.07184777633541162
trade_count: 3360
```

Dashboard URL:

```text
http://127.0.0.1:8000/ui/backtests/current
```

Dashboard smoke passed for current overview, nav, trades, and logs.

Benchmark note: this pilot run did not have local `000300.XSHG` benchmark price
data available in quant_platform. The engine therefore used
`benchmark_nav=1.0` fallback. Benchmark return, excess return and information
ratio from that run are not reliable benchmark conclusions.

## Reconciliation Notes

This pilot migrates only the Q5 target-weight generation logic from the legacy
script. It does not migrate `execute_rebalance`, `run_strategy`, benchmark NAV,
summary metrics, plotting, or report generation.

New platform results can differ from the legacy script because:

- the legacy script computes portfolio returns directly from return panels
- quant_platform simulates price-based execution, cash, 100-share lots,
  commission, tax, and slippage
- trading constraint handling and NAV timing can differ

Suggested next reconciliation steps:

- compare daily Q5 stock pools
- compare daily target weights
- compare position quantities after lot rounding
- compare trade counts
- compare NAV direction and explain differences from cash, lots, costs, and timing
- later support `ScoreLongOnly`
- keep `Q5MinusQ1` and `ScoreLongShort` out of V0 until the platform supports long-short
