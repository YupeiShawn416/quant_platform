# RQData HXZ Probe

Status: `success`

## API Capabilities

- `get_price`: True
- `get_factor`: True
- `get_all_factor_names`: True
- `get_financials`: False
- `query`: False
- `fundamentals`: False
- `get_turnover_rate`: True
- `all_instruments`: True

## Samples

### price_none

- status: success
- rows: 28
- columns: close, volume, total_turnover

### valuation_factor

- status: success
- rows: 28
- columns: market_cap, market_cap_2, pb_ratio, pe_ratio

### turnover_rate

- status: success
- rows: 28
- columns: today, week, month, year, current_year

### factor_names_sample

- status: success
- rows: 200
- columns: factor_name

