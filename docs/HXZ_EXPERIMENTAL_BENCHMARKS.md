# CN-HXZ and CN-FF3 Experimental Benchmarks

This project exposes two monthly experimental benchmark datasets:

- `cn_hxz_4_factors_monthly`
- `cn_ff3_factors_monthly`

Frequency: monthly.

Status: experimental, not production.

Construction rules:

- Formation uses point-in-time data visible before formation date.
- Same-day announcements are not assumed available at market open.
- Returns are value-weighted with lagged market capitalization in the main specification.
- CN-HXZ uses MKT, R_ME, R_IA, and R_ROE.
- CN-FF3 uses MKT, SMB, and HML.

Known limits:

- Sample starts in 2016-07 for completed annual grouping.
- These factors are research benchmarks and are not used automatically for strategy ranking.
- Robustness versions are documented in validation reports.

Data API examples:

```bash
curl "$QUANT_PLATFORM_API_URL/data/query/cn_hxz_4_factors_monthly?limit=5" \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN"

curl "$QUANT_PLATFORM_API_URL/data/query/cn_ff3_factors_monthly?limit=5" \
  -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN"
```

Regression use:

```python
from rq_platform.data.query_service import DataQueryService

hxz, _ = DataQueryService().query("cn_hxz_4_factors_monthly", limit=500)
ff3, _ = DataQueryService().query("cn_ff3_factors_monthly", limit=500)
```
