# HXZ PIT Sample Validation

## Verdict

The small-sample RQData validation passed.

The current RQData environment supports the key APIs needed for a credible China HXZ data build:

- `get_pit_financials_ex`: available
- `get_yield_curve`: available
- typed `get_all_factor_names(type="balance_sheet")`: available
- typed `get_all_factor_names(type="income_statement")`: available
- `get_factor` financial `_mrq_0` / `_lyr_0` fields: available

## Validated Financial Fields

Typed factor discovery confirmed:

Balance sheet candidates:

- `total_assets`
- `total_assets_mrq_0`
- `total_assets_lyr_0`
- `equity_parent_company`
- `equity_parent_company_mrq_0`
- `equity_parent_company_lyr_0`
- `total_equity`
- `total_equity_mrq_0`
- `total_equity_lyr_0`

Income statement candidates:

- `net_profit_parent_company`
- `net_profit_parent_company_mrq_0`
- `net_profit_parent_company_lyr_0`

`adjusted_net_profit_mrq_0` and `adjusted_net_profit_lyr_0` were callable but had 25% null rate in the 4-stock sample, so they should be secondary fields rather than the primary HXZ profitability input.

## get_factor Sample

Sample:

- symbols: `600519.XSHG`, `000001.XSHE`, `300750.XSHE`, `688001.XSHG`
- dates: `2025-01-02` to `2025-01-10`
- rows: 28
- fields: 9

Null rates:

| field | null rate |
| --- | ---: |
| total_assets_mrq_0 | 0.00 |
| total_assets_lyr_0 | 0.00 |
| equity_parent_company_mrq_0 | 0.00 |
| equity_parent_company_lyr_0 | 0.00 |
| total_equity_mrq_0 | 0.00 |
| net_profit_parent_company_mrq_0 | 0.00 |
| net_profit_parent_company_lyr_0 | 0.00 |
| adjusted_net_profit_mrq_0 | 0.25 |
| adjusted_net_profit_lyr_0 | 0.25 |

## PIT Statement Sample

`get_pit_financials_ex` returned explicit PIT metadata:

- `info_date`
- `rice_create_tm`
- `if_adjusted`
- `quarter`
- `order_book_id`

Sample query:

- quarters: `2024q3` to `2024q4`
- query date: `2025-01-10`
- statements: `latest`
- rows: 4

Returned columns:

- `info_date`
- `rice_create_tm`
- `if_adjusted`
- `equity_parent_company`
- `total_equity`
- `net_profit_parent_company`
- `total_assets`

This confirms that `get_pit_financials_ex` can be used to reconcile announcement dates and no-lookahead behavior for the daily `get_factor` PIT panel.

## Risk-Free Rate Sample

`get_yield_curve` returned China treasury yield curve data.

Sample:

- dates: `2025-01-02` to `2025-01-10`
- tenors: `0S`, `1M`, `3M`, `1Y`
- rows: 7

This is sufficient for an RMB risk-free rate dataset. The recommended first convention is to store all four tenors and let the HXZ factor builder choose the final tenor, with `1M` as the initial monthly excess-return candidate.

## Updated P0 Backfill Decision

Proceed to dry-run planning for these raw datasets:

1. `financial_pit_quarterly`
   - source: `get_pit_financials_ex`
   - key: `order_book_id`, `quarter`, `info_date`
   - fields: `total_assets`, `equity_parent_company`, `total_equity`, `net_profit_parent_company`, `if_adjusted`, `rice_create_tm`

2. `financial_factor_daily_pit`
   - source: `get_factor`
   - key: `trade_date`, `order_book_id`
   - fields: `total_assets_mrq_0`, `total_assets_lyr_0`, `equity_parent_company_mrq_0`, `equity_parent_company_lyr_0`, `total_equity_mrq_0`, `net_profit_parent_company_mrq_0`, `net_profit_parent_company_lyr_0`

3. `risk_free_rate`
   - source: `get_yield_curve`
   - key: `trade_date`
   - fields: `0S`, `1M`, `3M`, `1Y`

Do not use `adjusted_net_profit` as the primary field until its coverage is audited over a broader sample.
