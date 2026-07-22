# Benchmark Integration

- CN-HXZ: experimental benchmark
- CN-FF3: experimental benchmark
- Frequency: monthly
- PIT rule: formation-date-visible data only; no same-day announcement assumed before open
- Data API datasets: cn_hxz_4_factors_monthly, cn_ff3_factors_monthly
- Not production; do not auto-rank strategies with these factors.
- integration: {'registered_as_experimental_benchmark': True, 'hxz_better_than_ff3_primary': False, 'recommended_benchmark_stack': ['market_index_or_all_a_market', 'CAPM', 'CN_FF3', 'CN_HXZ', 'robustness_equal_weight_ex_small30_float_weight'], 'status': 'experimental', 'capm_mean_abs_alpha': 0.002938205180744534, 'ff3_mean_abs_alpha': 0.002929226472870214, 'hxz_mean_abs_alpha': 0.002504504176876998}
