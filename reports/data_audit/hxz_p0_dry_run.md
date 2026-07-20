# HXZ P0 Backfill Dry Run

run_id: `hxz_p0_plan_20260720_150623_245619`
data_root: `/Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata`
created_at: `2026-07-20T15:06:23`

## Summary

- datasets: 3
- symbols: 5554
- trading_dates: 2556
- quarters: 44
- estimated_api_calls: 627
- estimated_rows: 14491831

## Dataset Plans

| dataset | source_api | target_path | chunks | calls | rows | rough_disk | write_mode | status |
| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |
| financial_pit_quarterly | rqdatac.get_pit_financials_ex | `/Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata/financial_pit_quarterly` | 308 | 308 | 293251 | 30.2 MB | dry-run only; future year partition by info_date, append + deduplicate after key validation | planned |
| financial_factor_daily_pit | rqdatac.get_factor | `/Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata/financial_factor_daily_pit` | 308 | 308 | 14196024 | 1462.1 MB | dry-run only; future year partition by trade_date, append + deduplicate | planned |
| risk_free_rate | rqdatac.get_yield_curve | `/Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata/risk_free_rate` | 11 | 11 | 2556 | 209.7 KB | dry-run only; future year partition by trade_date, append + deduplicate | planned |

## Quality Checks

### financial_pit_quarterly
- required columns exist
- quarter format matches YYYYq[1-4]
- info_date is parseable and not earlier than quarter end without reason
- candidate primary keys are unique or version columns are retained
- multi-version rows are detected
- if_adjusted distribution is recorded
- numeric accounting fields are numeric
- total_assets is positive where present
- equity and profit coverage are reported

### financial_factor_daily_pit
- trade_date + order_book_id unique
- required fields exist
- primary field coverage is above smoke threshold
- dates are ordered per symbol
- PIT step-change counts are reported
- extreme values are flagged
- sample rows reconcile against quarterly PIT values
- new quarter values do not appear before info_date

### risk_free_rate
- trade_date unique
- tenor fields exist
- unit is inferred and recorded
- values are in a reasonable rate range
- missing dates are reported
- term-structure anomalies are warned
