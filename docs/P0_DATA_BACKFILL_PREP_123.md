# P0 Data Backfill Prep: Daily PIT Factors, Corporate Actions, Financial PIT Expansion

Prepared on 2026-07-23 for the server data lake at `/opt/quant_platform`.

This is a pre-backfill checklist only. No full backfill was executed while
preparing this document. A limited RQData schema probe was run on three symbols
to validate function availability and output shapes.

## Current Server Baseline

The server already exposes these relevant datasets through the Data API:

| dataset | rows | date column | coverage |
| --- | ---: | --- | --- |
| `prices_1d_pre` | 10,791,638 | `trade_date` | 2016-01-04 to 2026-07-21 |
| `valuation_1d` | 10,796,835 | `trade_date` | 2016-01-04 to 2026-07-22 |
| `tradability_1d` | 10,847,393 | `trade_date` | 2016-01-04 to 2026-07-22 |
| `industry_classification` | 10,785,075 | `trade_date` | 2016-01-04 to 2026-07-22 |
| `financial_pit_field_pack` | 580,390 | `info_date` | 2016-04-08 to 2026-07-22 |
| `financial_cashflow_field_pack` | 580,404 | `info_date` | 2016-04-08 to 2026-07-23 |
| `financial_pit_quarterly` | 641,428 | `info_date` | 2015-01-15 to 2026-07-14 |

## Limited RQData Probe Summary

Validated callable functions:

- `rqdatac.get_factor`
- `rqdatac.get_pit_financials_ex`
- `rqdatac.get_shares`
- `rqdatac.get_dividend`
- `rqdatac.get_dividend_info`
- `rqdatac.get_dividend_amount`
- `rqdatac.get_split`
- `rqdatac.get_ex_factor`
- `rqdatac.get_restricted_shares`
- `rqdatac.get_share_transformation`

Probe output was written locally to
`reports/generated/p0_123_rqdata_prep_probe.csv`; it is a generated report and
must not be committed.

## 1. `financial_factor_daily_pit`

### Objective

Build a reusable daily PIT factor table for factor research so downstream users
do not need to repeatedly align quarterly PIT statements to daily trading dates.

### Proposed Dataset

| item | value |
| --- | --- |
| dataset | `financial_factor_daily_pit` |
| storage | `data/research_data/rqdata/financial_factor_daily_pit/year=<YYYY>/financial_factor_daily_pit.parquet` |
| source | `rqdatac.get_factor` |
| date column | `trade_date` |
| primary key | `trade_date + order_book_id` |
| initial scope | A-share universe, 2016-01-04 to latest complete date |
| batch plan | 200 symbols x 1 calendar year per call window |
| overwrite rule | overwrite first year only when explicitly confirming a full rebuild |

### Tier A Fields: High Confidence, Probe-Validated

These fields returned from a limited sample call for
`2026-04-20` to `2026-04-30`.

| canonical field | RQData field | use case |
| --- | --- | --- |
| `total_assets_mrq` | `total_assets_mrq_0` | size, asset growth, leverage denominator |
| `equity_parent_company_mrq` | `equity_parent_company_mrq_0` | book equity, HML, ROE denominator |
| `total_equity_mrq` | `total_equity_mrq_0` | book capital, leverage |
| `net_profit_parent_company_mrq` | `net_profit_parent_company_mrq_0` | profitability, ROE numerator |
| `gross_profit_margin_ttm` | `gross_profit_margin_ttm` | profitability / quality |
| `net_profit_margin_ttm` | `net_profit_margin_ttm` | profitability / quality |
| `debt_to_asset_ratio_mrq` | `debt_to_asset_ratio_mrq_0` | balance sheet leverage |
| `current_ratio_mrq` | `current_ratio_mrq_0` | liquidity |
| `pe_ttm` | `pe_ttm` | valuation |
| `pcf_ttm` | `pcf_ttm` | valuation |
| `ps_ttm` | `ps_ttm` | valuation |

### Tier B Fields: Factor-Name Valid, Need Non-Null Probe

These names are present in `get_all_factor_names()` or are likely useful, but
need a non-null coverage probe across more dates/sectors before formal
backfill.

| canonical field | RQData field | note |
| --- | --- | --- |
| `current_ratio_ttm` | `current_ratio_ttm` | liquidity ratio |
| `quick_ratio_ttm` | `quick_ratio_ttm` | stricter liquidity |
| `cash_ratio_ttm` | `cash_ratio_ttm` | cash liquidity |
| `debt_to_asset_ratio_ttm` | `debt_to_asset_ratio_ttm` | leverage |
| `debt_to_equity_ratio_ttm` | `debt_to_equity_ratio_ttm` | leverage |
| `equity_multiplier_ttm` | `equity_multiplier_ttm` | DuPont leverage |
| `interest_bearing_debt_ttm` | `interest_bearing_debt_ttm` | debt burden |
| `net_debt_ttm` | `net_debt_ttm` | EV/net debt |
| `working_capital_ttm` | `working_capital_ttm` | quality / accrual |
| `net_working_capital_ttm` | `net_working_capital_ttm` | quality / accrual |
| `invested_capital_ttm` | `invested_capital_ttm` | ROIC denominator |
| `operating_cash_flow_per_share_ttm` | `operating_cash_flow_per_share_ttm` | cash profitability |
| `free_cash_flow_company_per_share_ttm` | `free_cash_flow_company_per_share_ttm` | FCF proxy |
| `free_cash_flow_equity_per_share_ttm` | `free_cash_flow_equity_per_share_ttm` | equity FCF proxy |
| `book_value_per_share_ttm` | `book_value_per_share_ttm` | value |
| `tangible_asset_per_share_ttm` | `tangible_asset_per_share_ttm` | asset backing |
| `operating_revenue_growth_ratio_ttm` | `operating_revenue_growth_ratio_ttm` | growth |
| `net_profit_growth_ratio_ttm` | `net_profit_growth_ratio_ttm` | growth |
| `net_profit_parent_company_growth_ratio_ttm` | `net_profit_parent_company_growth_ratio_ttm` | growth |
| `total_asset_growth_ratio_ttm` | `total_asset_growth_ratio_ttm` | investment |
| `net_operate_cash_flow_growth_ratio_ttm` | `net_operate_cash_flow_growth_ratio_ttm` | cashflow growth |

### Pre-Backfill Probe

Run before writing any parquet:

```bash
ENABLE_RQDATA_PROBE=1 PYTHONPATH=src /opt/miniconda3/envs/quant_platform/bin/python \
  scripts/<new_probe_script>.py \
  --dataset financial_factor_daily_pit \
  --start-date 2026-04-01 \
  --end-date 2026-04-30 \
  --symbols 000001.XSHE,600519.XSHG,300750.XSHE,688981.XSHG,000852.XSHE \
  --fields <tier_a_and_tier_b_fields>
```

Probe acceptance:

- At least 5 symbols and 15 trading dates.
- No auth, quota, permission, timeout, or schema error.
- Required keys normalize to `trade_date + order_book_id`.
- Each Tier A field has non-null coverage on at least one sampled stock-date.
- Tier B fields are classified as `available_non_null`, `available_empty`, or
  `unavailable`; only `available_non_null` fields enter first full backfill.

### Quality Gates

- Duplicate `trade_date + order_book_id` must be zero.
- `trade_date` must be in trading calendar.
- `order_book_id` must exist in instruments.
- Report null rates by year and field.
- For overlapping fields in `valuation_1d`, reconcile `pe_ttm`, `pcf_ttm`, and
  `ps_ttm` if names overlap or are reintroduced.

### Full Backfill Order

1. Dry-run full scope.
2. Smoke: 6 symbols, one month.
3. Real backfill by year: 2016, 2017, ..., 2026.
4. Run check and audit after every two years.
5. Expose through `DATASET_SPECS` only after local quality passes.

Stop immediately on auth, quota, timeout, schema drift, duplicate keys, or
unexpected all-null Tier A fields.

## 2. Corporate Actions, Dividends, Share Capital

### Objective

Create event and daily/month-end share-capital datasets to support dividend
yield, buyback/dilution, adjusted return checks, market-cap accuracy, and
corporate action event studies.

### Proposed Datasets

| dataset | source | date column | primary key | grain |
| --- | --- | --- | --- | --- |
| `share_capital_daily` | `rqdatac.get_shares` | `trade_date` | `trade_date + order_book_id` | daily stock share capital |
| `corporate_dividend_events` | `rqdatac.get_dividend_info` | `info_date` | `order_book_id + sequence_num + info_date` | dividend announcement / event |
| `corporate_dividend_amount_pit` | `rqdatac.get_dividend_amount` | `info_date` | `order_book_id + quarter + event_procedure + info_date` | PIT dividend amount |
| `corporate_split_events` | `rqdatac.get_split` | `ex_dividend_date` | `order_book_id + ex_dividend_date + book_closure_date` | split / transfer event |
| `corporate_ex_factor_events` | `rqdatac.get_ex_factor` | `ex_date` | `order_book_id + ex_date + announcement_date` | ex-right/ex-dividend factor event |
| `restricted_share_unlock_events` | `rqdatac.get_restricted_shares` | TBD after probe | TBD after probe | restricted-share unlock event |
| `share_transformation_events` | `rqdatac.get_share_transformation` | `effective_date` | `predecessor + successor + effective_date` | code conversion / merger event |

### `share_capital_daily`

Probe-returned columns from `get_shares`:

| canonical field | source column | note |
| --- | --- | --- |
| `trade_date` | `date` | normalize from source |
| `order_book_id` | `order_book_id` | stock id |
| `total_share` | `total` | total shares |
| `circulation_a_share` | `circulation_a` | A-share circulating shares |
| `non_circulation_a_share` | `non_circulation_a` | non-circulating A shares |
| `total_a_share` | `total_a` | total A shares |
| `preferred_shares` | `preferred_shares` | preferred shares |
| `free_circulation_share` | `free_circulation` | free float style field |

Recommended storage:

```text
data/research_data/rqdata/share_capital_daily/year=<YYYY>/share_capital_daily.parquet
```

Quality gates:

- Duplicate `trade_date + order_book_id` is zero.
- Share fields are non-negative.
- `free_circulation_share <= circulation_a_share <= total_a_share <= total_share`
  when all components are non-null.
- Reconcile with `valuation_1d.market_cap / close` on sampled dates where
  possible.

### `corporate_dividend_events`

Prefer `get_dividend_info` over `get_dividend` for first event table because it
includes `info_date`, `effective_date`, `sequence_num`, `special_dividend`, and
`rice_create_tm`.

Probe-returned columns:

| canonical field | source column |
| --- | --- |
| `order_book_id` | `order_book_id` |
| `effective_date` | `effective_date` |
| `info_date` | `info_date` |
| `ex_dividend_date` | `ex_dividend_date` |
| `dividend_bonus_share` | `dividend_bonus_share` |
| `dividend_transferred_share` | `dividend_transferred_share` |
| `dividend_cash_before_tax` | `dividend_cash_before_tax` |
| `dividend_type` | `dividend_type` |
| `sequence_num` | `sequence_num` |
| `special_dividend` | `special_dividend` |
| `rice_create_tm` | `rice_create_tm` |

Also keep a raw cross-check table from `get_dividend` during smoke:

- `declaration_announcement_date`
- `book_closure_date`
- `dividend_cash_before_tax`
- `ex_dividend_date`
- `payable_date`
- `advance_date`
- `round_lot`
- `quarter`

Quality gates:

- `info_date <= ex_dividend_date` when both are non-null; exceptions must be
  counted and reviewed.
- `dividend_cash_before_tax >= 0`.
- `sequence_num` participates in the key because multiple events can share a
  date.
- Reconcile event counts and cash fields between `get_dividend` and
  `get_dividend_info` on the smoke universe.

### `corporate_dividend_amount_pit`

Source: `get_dividend_amount`.

Probe-returned columns:

- `order_book_id`
- `quarter`
- `event_procedure`
- `info_date`
- `amount`
- `rice_create_tm`

Use this as the PIT dividend amount table, not as the primary event calendar.

Quality gates:

- Duplicate `order_book_id + quarter + event_procedure + info_date` is zero, or
  add `rice_create_tm` if needed after smoke.
- Amount is non-negative.
- Reconcile annual/quarter amount with aggregated dividend events where
  possible.

### Split, Ex-Factor, Restricted Shares, Transformation

Source-specific notes:

| dataset | probe status | fields to keep | pre-backfill note |
| --- | --- | --- | --- |
| `corporate_split_events` | non-empty on sample | `ex_dividend_date`, `book_closure_date`, `split_coefficient_to`, `payable_date`, `split_coefficient_from`, `cum_factor` | sparse event table; use long historical window in smoke |
| `corporate_ex_factor_events` | non-empty on sample | `ex_date`, `announcement_date`, `ex_cum_factor`, `ex_end_date`, `ex_factor` | useful for adjustment audit |
| `restricted_share_unlock_events` | callable but sample empty | source columns TBD | run a broader 2016-2026 probe before implementation |
| `share_transformation_events` | non-empty full table | `predecessor`, `successor`, `effective_date`, `share_conversion_ratio`, `predecessor_delisted`, `predecessor_delisted_date`, `event` | not symbol-batched; store once as dimension/event table |

### Pre-Backfill Probe

Recommended smoke symbols:

```text
000001.XSHE,000002.XSHE,600519.XSHG,300750.XSHE,688981.XSHG,601318.XSHG
```

Recommended probe windows:

- `get_shares`: 2026-04-01 to 2026-04-30.
- `get_dividend`, `get_dividend_info`, `get_restricted_shares`: 2024-01-01 to
  2026-07-23.
- `get_split`, `get_ex_factor`: 2016-01-01 to 2026-07-23 because events are
  sparse.
- `get_share_transformation`: one full-table call.

Stop immediately on auth, quota, timeout, permission, schema drift, or empty
result for `get_shares`.

## 3. Financial PIT Expansion Pack 2

### Objective

Extend the current PIT financial statement coverage beyond the first core pack
and cashflow pack. This unlocks accruals, working capital, expense structure,
asset quality, operating efficiency, and more robust FCF proxies.

### Proposed Dataset

| item | value |
| --- | --- |
| dataset | `financial_pit_expansion_field_pack` |
| storage | `data/research_data/rqdata/financial_pit_expansion_field_pack/year=<YYYY>/financial_pit_expansion_field_pack.parquet` |
| source | `rqdatac.get_pit_financials_ex` |
| date column | `info_date` |
| primary key | `order_book_id + report_period + info_date` plus `statement_type` if populated |
| initial scope | A-share universe, 2016q1 to 2026q3 |
| batch plan | 200 symbols x quarter range |

### Tier A Fields: First Expansion

Use source field names as canonical when RQData names are already stable.
Fields must still pass a limited RQData probe before full backfill.

| category | fields |
| --- | --- |
| receivables / prepayments | `accounts_receivable`, `notes_receivable`, `accounts_receivable_and_notes_receivable`, `prepayments`, `other_receivables` |
| payables / advances | `accounts_payable`, `notes_payable`, `accounts_payable_and_notes_payable`, `advance_receipts`, `other_payables` |
| assets | `fixed_assets`, `construction_in_process`, `investment_property`, `long_term_equity_investment`, `deferred_tax_assets` |
| liabilities | `short_term_loans`, `long_term_loans`, `bonds_payable`, `non_current_liabilities_due_within_one_year`, `deferred_tax_liabilities` |
| income statement | `operating_cost`, `operating_profit`, `total_profit`, `income_tax_expense`, `deduct_net_profit_parent` |
| expenses | `sales_expense`, `admin_expense`, `financial_expense`, `rd_expense` |
| cashflow support | `depreciation_amortization`, `dividends_paid` |

### Tier B Fields: Validate Names Before Use

Some desired canonical concepts may map to different RQData names. Probe exact
field names before adding them:

| canonical concept | candidate names / source |
| --- | --- |
| capex | prefer cashflow pack `cash_paid_for_asset`; validate if `capex` exists in PIT fields before using |
| cash and equivalents | cashflow pack has `cash_equivalent`, `end_period_cash_equivalent`; validate balance-sheet equivalent separately |
| minority interest | probe possible equity statement names before use |
| impairment / asset write-down | probe exact statement names before use |
| tax payable | probe exact liability field name |

### Pre-Backfill Probe

```bash
PYTHONPATH=src /opt/miniconda3/envs/quant_platform/bin/python \
  scripts/<new_probe_script>.py \
  --dataset financial_pit_expansion_field_pack \
  --start-quarter 2024q1 \
  --end-quarter 2025q4 \
  --symbols 000001.XSHE,000002.XSHE,600519.XSHG,300750.XSHE,688981.XSHG,601318.XSHG \
  --fields <tier_a_fields>
```

Probe acceptance:

- No invalid-field errors from RQData.
- At least one non-null observation for every Tier A field, or the field is
  explicitly downgraded to Tier B.
- Duplicate keys are zero under the current key rule.
- `info_date` is never earlier than report period end.
- `field_mapping_json` is present and records canonical-to-source mapping.

### Full Backfill Order

Use the same staged dates as the completed financial/cashflow packs:

1. 2016-01-01 to 2018-12-31.
2. 2019-01-01 to 2021-12-31.
3. 2022-01-01 to 2024-12-31.
4. 2025-01-01 to latest allowed date.

Run check and audit after every stage. Do not expose the dataset in the API
until quality is zero-error.

## Implementation Readiness Tasks

Before any full backfill, implement these small pieces:

1. Add a generic limited RQData probe script for the three pack types.
2. Add plan modules:
   - `financial_factor_daily_pit_plan.py`
   - `corporate_actions_plan.py`
   - `financial_pit_expansion_field_pack_plan.py`
3. Add dry-run-only Make targets:
   - `probe-financial-factor-daily-pit`
   - `probe-corporate-actions`
   - `probe-financial-pit-expansion-field-pack`
4. Add quality checks:
   - duplicate key checks
   - date parse and date-range checks
   - non-negative checks for shares/dividends
   - null-rate summaries by year and field
5. Add API specs only after local backfill smoke passes.

## Safety Rules

- Do not commit `data/`, parquet, `runs/`, zip files, or `reports/generated/`.
- Do not print RQData credentials.
- Do not push without explicit request.
- Stop on auth, quota, timeout, permission, field-missing, schema drift,
  duplicate-key, or all-null required-field errors.
- Backfill in staged chunks only; never launch 2016-present full scope in one
  blind command.
