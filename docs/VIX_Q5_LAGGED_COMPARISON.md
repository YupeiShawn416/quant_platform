# VIX Q5 Same-Day vs Lagged Comparison

## Runs

- Same-day run_id: `vix_beta_q5_long_only_2025`
- Lagged run_id: `vix_beta_q5_long_only_2025_lagged`
- Same-day benchmark reliable: `True`
- Lagged benchmark reliable: `True`

## Metrics

| Metric | Same-Day | Lagged | Difference (Lagged - Same-Day) |
|---|---:|---:|---:|
| total_return | 0.399575 | 0.412844 | 0.013269 |
| annual_return | 0.419152 | 0.433166 | 0.014014 |
| sharpe | 2.777681 | 2.846144 | 0.068463 |
| max_drawdown | -0.074243 | -0.082404 | -0.008161 |
| benchmark_return | 0.211901 | 0.211901 | 0.000000 |
| excess_return | 0.187674 | 0.200944 | 0.013269 |
| tracking_error | 0.088519 | 0.090357 | 0.001838 |
| information_ratio | 1.696813 | 1.773367 | 0.076555 |
| trade_count | 3322.000000 | 3336.000000 | 14.000000 |

## Interpretation

The lagged package shifts each target-weight date to the next local trading date. This is a stricter timing assumption than same-day close-to-close execution and is intended to reveal whether same-day signal usage materially inflates apparent performance.
