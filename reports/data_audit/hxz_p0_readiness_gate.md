# HXZ P0 Backfill Readiness Gate

decision: CONDITIONAL GO
recommended_scheme: B
rqdata_calls_this_gate: 21

## PIT Timing
- events: 20
- non_trading_events: 10 pass_rate=0.0
- trading_day_events: 10 pass_rate=1.0
- non_trading_updates_previous_trade_date: True
- no_early_use_confirmed_for_trading_day_info_date: True
- non-trading info_date convention: sampled weekend announcements were already reflected on the previous trading-date factor panel, likely because RQData ingested the report after that trading day's close. Treat get_factor dates as after-close PIT snapshots, not intraday-available values.
- monthly PIT rule: for month-end sorts, use the latest PIT values available after the last trading day's close; for month-start formation, use the previous trading day's after-close PIT snapshot.

## Version Key
- selected_key: order_book_id+quarter+info_date
- multi_version_stock_quarters: 1125
- value_changed_stock_quarters: 171

## Backfill Order
1. risk_free_rate
2. financial_pit_quarterly
3. financial_factor_daily_pit or monthly PIT snapshots

## Safety Thresholds
- financial_pit_quarterly: stop after 30 failed chunks or any auth/quota error.
- financial_factor_daily_pit: stop after 30 failed chunks or any auth/quota error.
- risk_free_rate: stop after 5 failed chunks or any auth/quota error.

No full backfill was executed. No formal parquet partitions were written.
