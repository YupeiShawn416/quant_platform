# HXZ RQData Manual Review

Source PDFs reviewed from `/Users/yupeishen/Documents/Tools/dynamichtml2pdf-main`:

- `stock-mod.pdf`
- `generic-api.pdf`
- `macro-economy.pdf`

## Verdict

RQData documentation supports a credible path for China HXZ replication, but the correct raw data path is not only `get_factor`.

Use two layers:

1. `get_factor` for PIT-processed daily financial factor panels such as `_mrq_n`, `_lyr_n`, and `_ttm_n`.
2. `get_pit_financials_ex` for quarterly base financial statements with explicit `quarter`, `info_date`, and `if_adjusted`.

For the risk-free rate, use `get_yield_curve` from the generic API, not stock factor names.

## Financial Statement Evidence

The stock manual documents `get_pit_financials_ex(order_book_ids, fields, start_quarter, end_quarter, date, statements, market)`.

Important returned fields:

- `quarter`
- `info_date`: announcement publication date
- requested financial fields
- `if_adjusted`

The manual states the API queries quarterly base financial data in point-in-time form. This is the strongest candidate for HXZ audit-quality accounting data because it gives both report period and actual available date.

## Financial Factor Evidence

The stock manual documents `get_factor(order_book_ids, factor, start_date, end_date, ...)`.

It says financial, technical, and Alpha101 factors are supported. It also documents:

- `_mrq_n`: most recent quarter series
- `_ttm_n`: trailing twelve months series
- `_lyr_n`: latest annual report series

The manual describes PIT handling for `_mrq_n` financial data and explicitly frames it as avoiding future data. This supports using fields such as:

- `total_assets_mrq_0`
- `total_assets_lyr_0`
- `equity_parent_company_mrq_0`
- `equity_parent_company_lyr_0`
- `net_profit_parent_company_mrq_0`
- `adjusted_net_profit_mrq_0`

However, `get_factor` does not expose `info_date` in the returned panel. For HXZ replication, this means `get_factor` is convenient for daily PIT values, while `get_pit_financials_ex` is still needed to validate and reconcile announcement timing.

## Factor Name Discovery

The stock manual documents `get_all_factor_names(type=None, market='cn')` and supports type filters:

- `income_statement`
- `balance_sheet`
- `cash_flow_statement`
- `eod_indicator`
- `operational_indicator`
- `cash_flow_indicator`
- `financial_indicator`
- `growth_indicator`

This confirms that the next probe should use typed factor discovery rather than only keyword searching all names.

## Risk-Free Rate Evidence

The generic API manual documents `get_yield_curve(start_date=None, end_date=None, tenor=None, market='cn')`.

It returns China treasury yield curve data from 2002 onward and is described as a risk-free yield curve. Candidate tenors for HXZ monthly excess return:

- `0S`
- `1M`
- `3M`
- `1Y`

The macro manual also documents repo-rate APIs:

- `econ.get_fixing_repo_rate`
- `econ.get_interbank_pledged_repo_rate`

For HXZ, `get_yield_curve` is the cleaner first choice unless the paper's China replication convention explicitly prefers repo rates.

## Updated HXZ Data Decision

| Requirement | Decision |
| --- | --- |
| Monthly stock returns | Use local `prices_1d_none`; derive monthly total return. |
| Previous month-end market cap | Use local `valuation_1d.market_cap`; reconcile units with RQData. |
| Annual total assets | Use `get_factor total_assets_lyr_0` for daily PIT panel; validate with `get_pit_financials_ex total_assets`. |
| Prior-year total assets | Derive from annual total assets / `total_assets_lyr_n`. |
| Quarterly profit | Use `net_profit_parent_company_mrq_0` or `adjusted_net_profit_mrq_0`; validate against `get_pit_financials_ex`. |
| Book equity | Use `equity_parent_company_mrq_0` or `total_equity_mrq_0`; validate with PIT base financials. |
| Announcement date | Use `get_pit_financials_ex.info_date`; not available in `get_factor` output. |
| Financial industry flag | Use local `instruments.sector_code` and `industry_classification`. |
| Risk-free rate | Use `get_yield_curve`, likely `1M` or `0S` depending convention. |

## Sample Probe Result

The follow-up small-sample probe passed:

1. `rqdatac.get_pit_financials_ex` exists.
2. `rqdatac.get_yield_curve` exists.
3. Typed factor discovery confirms the required balance-sheet and income-statement fields.
4. `get_factor` returns non-null values for the primary fields in a 4-stock sample.
5. `get_pit_financials_ex` returns `info_date`, `rice_create_tm`, `if_adjusted`, `quarter`, and requested accounting fields.
6. `get_yield_curve` returns `0S`, `1M`, `3M`, and `1Y` for the sample date range.

Detailed result: `reports/data_audit/hxz_pit_sample_validation.md`.

## Next Step

Proceed to a dry-run backfill plan for:

- `financial_pit_quarterly`
- `financial_factor_daily_pit`
- `risk_free_rate`
