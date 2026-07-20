# HXZ Reconciliation

This file reconciles current local data against the minimum inputs needed for China HXZ four-factor replication.

## Current Local State

- `instruments`: rows=5554, symbols=5554, range=1990-12-01 to 2026-07-02, files=1
- `trading_calendar`: rows=2556, symbols=None, range=2016-01-04 to 2026-07-14, files=1
- `prices_1d_none`: rows=10765635, symbols=5449, range=2016-01-04 to 2026-07-14, files=11
- `prices_1d_pre`: rows=10765635, symbols=5449, range=2016-01-04 to 2026-07-14, files=11
- `index_prices_1d`: rows=15336, symbols=6, range=2016-01-04 to 2026-07-14, files=11
- `tradability_1d`: rows=10816073, symbols=5465, range=2016-01-04 to 2026-07-14, files=11
- `valuation_1d`: rows=10765631, symbols=5449, range=2016-01-04 to 2026-07-14, files=11
- `industry_classification`: rows=10753829, symbols=5452, range=2016-01-04 to 2026-07-14, files=11
- `index_components`: rows=4600800, symbols=3379, range=2016-01-04 to 2026-07-14, files=11
- `index_weights`: rows=4600800, symbols=3379, range=2016-01-04 to 2026-07-14, files=11
- `intraday_snapshots`: rows=4416972, symbols=5174, range=2025-01-02 to 2025-08-29, files=8

## Blocking Gaps

- `annual_total_assets`: local parquet missing; RQData get_factor candidates include total_assets, total_assets_lyr_0, and total_assets_mrq_0, but announce-date semantics still need validation.
- `prior_year_total_assets`: derive from total_assets_lyr_0 or materialized annual total assets after PIT semantics are validated.
- `single_quarter_profit`: local parquet missing; RQData get_factor candidates include net_profit_parent_company_mrq_0 and adjusted_net_profit_mrq_0, but quarter convention needs validation.
- `previous_quarter_book_equity`: local parquet missing; RQData get_factor candidates include equity_parent_company_mrq_0 and total_equity_mrq_0, but announce-date semantics still need validation.
- `real_announcement_date`: not found in get_all_factor_names keyword searches for announce, announcement, pub, or report.
- `positive_negative_book_equity`: depends on book equity backfill.
- `rmb_risk_free_rate`: not found in get_all_factor_names keyword searches for risk_free, rf, shibor, or treasury-rate style names.

## Probe Dependency

RQData small-sample probing is still required to confirm financial statement APIs, announcement-date semantics, cumulative versus single-quarter fields, and risk-free source availability.
