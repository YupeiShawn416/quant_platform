# HXZ Quota Assessment

quota_status: no documented SDK quota endpoint used; only successful limited calls and prior RQData errors are available

## Plan
- financial_pit_quarterly: calls=308, rows=293251, max_batch_rows=1600, runtime_min=46, stop_after_failures=30
- financial_factor_daily_pit: calls=308, rows=14196024, max_batch_rows=50400, runtime_min=46, stop_after_failures=30
- risk_free_rate: calls=11, rows=2556, max_batch_rows=252, runtime_min=1, stop_after_failures=5

## Schemes
- A: {'api_calls': 627, 'estimated_rows': 14491831, 'disk': 'about 1.5 GB plus parquet overhead', 'impact': 'maximizes data lake reuse and daily PIT research convenience'}
- B: {'api_calls': 330, 'estimated_rows': 962287, 'disk': 'roughly 100 MB plus monthly snapshot overhead', 'impact': 'sufficient for HXZ monthly replication; delays reusable daily financial PIT panel'}
