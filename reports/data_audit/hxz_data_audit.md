# HXZ Data Audit

Data root: `/Users/yupeishen/Desktop/quant_platform/data/research_data/rqdata`
Generated at: `2026-07-20T13:48:54.902312+08:00`

## Verdict

Local A-share daily market data is strong enough for returns, market-cap sorts, tradability filters, and industry diagnostics, but it is not yet sufficient for a credible China HXZ four-factor replication because PIT financial statement fields, announcement dates, book equity, quarterly profit, and RMB risk-free rate are missing.

## Dataset Coverage

| dataset | files | rows | symbols | date range | duplicate keys | key columns |
| --- | ---: | ---: | ---: | --- | ---: | --- |
| instruments | 1 | 5554 | 5554 | 1990-12-01 to 2026-07-02 | 0 | order_book_id |
| trading_calendar | 1 | 2556 |  | 2016-01-04 to 2026-07-14 | 0 | trade_date |
| prices_1d_none | 11 | 10765635 | 5449 | 2016-01-04 to 2026-07-14 | 0 | trade_date, order_book_id, adjust_type |
| prices_1d_pre | 11 | 10765635 | 5449 | 2016-01-04 to 2026-07-14 | 0 | trade_date, order_book_id, adjust_type |
| index_prices_1d | 11 | 15336 | 6 | 2016-01-04 to 2026-07-14 | 0 | trade_date, order_book_id |
| tradability_1d | 11 | 10816073 | 5465 | 2016-01-04 to 2026-07-14 | 0 | trade_date, order_book_id |
| valuation_1d | 11 | 10765631 | 5449 | 2016-01-04 to 2026-07-14 | 0 | trade_date, order_book_id |
| industry_classification | 11 | 10753829 | 5452 | 2016-01-04 to 2026-07-14 | 0 | trade_date, order_book_id, industry_system, industry_level |
| index_components | 11 | 4600800 | 3379 | 2016-01-04 to 2026-07-14 | 0 | trade_date, index_id, order_book_id |
| index_weights | 11 | 4600800 | 3379 | 2016-01-04 to 2026-07-14 | 0 | trade_date, index_id, order_book_id |
| intraday_snapshots | 8 | 4416972 | 5174 | 2025-01-02 to 2025-08-29 | 0 | trade_date, snapshot_time, order_book_id |

## HXZ Field Matrix

| requirement | status | local dataset | fields | priority | gap |
| --- | --- | --- | --- | --- | --- |
| monthly_total_return | derivable | prices_1d_none | trade_date, order_book_id, close | P0 | daily return and monthly total return are not materialized; derive from unadjusted close with corporate-action checks. |
| previous_month_end_market_cap | available | valuation_1d | market_cap, float_market_cap | P0 | share-count provenance and units need RQData confirmation. |
| annual_total_assets | missing |  |  | P0 | local parquet missing; RQData get_factor candidates include total_assets, total_assets_lyr_0, and total_assets_mrq_0, but announce-date semantics still need validation. |
| prior_year_total_assets | missing |  |  | P0 | derive from total_assets_lyr_0 or materialized annual total assets after PIT semantics are validated. |
| single_quarter_profit | missing |  |  | P0 | local parquet missing; RQData get_factor candidates include net_profit_parent_company_mrq_0 and adjusted_net_profit_mrq_0, but quarter convention needs validation. |
| previous_quarter_book_equity | missing |  |  | P0 | local parquet missing; RQData get_factor candidates include equity_parent_company_mrq_0 and total_equity_mrq_0, but announce-date semantics still need validation. |
| real_announcement_date | missing |  |  | P0 | not found in get_all_factor_names keyword searches for announce, announcement, pub, or report. |
| industry_and_financial_flag | available | industry_classification, instruments | industry_system, industry_level, industry_code, industry_name, sector_code | P0 | financial flag can be derived, but HXZ replication rule must choose a canonical industry system. |
| positive_negative_book_equity | missing |  |  | P0 | depends on book equity backfill. |
| listing_delisting_status | partial | instruments, tradability_1d | listed_date, de_listed_date, status, is_listed, is_suspended, is_st | P1 | static instruments plus daily tradability exist; full status history semantics need probe. |
| a_share_market_return | derivable | prices_1d_none, valuation_1d, index_prices_1d | close, market_cap, index close | P0 | HXZ all-A value-weighted market return should be materialized and reconciled against broad indices. |
| rmb_risk_free_rate | missing |  |  | P0 | not found in get_all_factor_names keyword searches for risk_free, rf, shibor, or treasury-rate style names. |

## Cross Checks

- prices_vs_valuation: warning (left_only=4, right_only=0, overlap=10765631)
- prices_vs_tradability: warning (left_only=4, right_only=50442, overlap=10765631)
- instrument_financial_and_special_type: ok (financial_instruments=119, non_normal_special_type=486)

## Immediate Missing P0 Data

- financial_balance_sheet_pit: annual total assets, prior-year total assets, book equity / parent equity, announce date
- financial_income_statement_pit: single-quarter profit and parent net profit for ROE
- risk_free_rate: RMB risk-free rate for excess returns
- monthly_hxz_inputs: materialized monthly returns, previous month-end ME, accounting lags, and filters
