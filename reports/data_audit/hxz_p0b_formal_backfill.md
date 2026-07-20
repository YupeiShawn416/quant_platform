# HXZ P0B Formal Backfill

status: success
rqdata_calls: 347
succeeded_chunks: 347
failed_chunks: 0
empty_chunks: 0
skipped_chunks: 0

## Datasets
### risk_free_rate
- path: /Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata/risk_free_rate
- rows: 2632
- min_date: 2016-01-04
- max_date: 2026-07-14
- disk_bytes: 149875
- checksum: 1255ea3036565bc982661601658eff24e0c286dc2b8979e33189411cd8625e37
- null_rates: {'0S': 0.0, '1M': 0.0, '3M': 0.0, '1Y': 0.0}

### financial_pit_quarterly
- path: /Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata/financial_pit_quarterly
- rows: 641428
- min_date: 2015-01-15
- max_date: 2026-07-14
- disk_bytes: 21866754
- checksum: 4d24e720b7c734ffac27bf2812eb148d5e8ec6ced26443efeac12a842a985d25
- symbols: 5498
- quarters: 46
- multi_version_stock_quarters: 190905
- if_adjusted_distribution: {'1': 369345, '0': 272083}
- null_rates: {'total_assets': 0.012949, 'equity_parent_company': 0.015016, 'total_equity': 0.013135, 'net_profit_parent_company': 0.001819}

No financial_factor_daily_pit full backfill was executed.

## Quality Report Files

- reports/data_audit/hxz_risk_free_rate_quality.md
- reports/data_audit/hxz_financial_pit_quarterly_quality.md
- reports/data_audit/hxz_p0b_reconciliation.md
- reports/data_audit/hxz_p0b_backfill_manifest.json
