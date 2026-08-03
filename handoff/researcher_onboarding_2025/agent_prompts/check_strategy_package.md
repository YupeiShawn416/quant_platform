# Agent Prompt: Check Strategy Package

You are auditing a Quant Platform Strategy Package before submission.

Inspect only the package files and the local sample project outputs. Do not read
`.env`, browser state, SSH keys, or private notes.

Check:

- `strategy_package.zip` exists.
- `manifest.json` exists and declares `mode=weights`.
- `config.json` includes `run_id`, `strategy_name`, `start_date`, `end_date`,
  `initial_cash`, `benchmark`, `adjust_type`, `frequency`, `commission_rate`,
  `tax_rate`, `slippage_rate`, `lot_size`, and `price_field`.
- `weights.csv` or `weights.parquet` exists.
- weights include `trade_date`, `order_book_id`, and `target_weight`.
- dates are parseable.
- `target_weight` values are numeric and non-negative.
- there are no duplicate `trade_date/order_book_id` rows.
- each daily `target_weight` sum is less than or equal to `1.0`.
- package does not contain raw market data, API token, `.env`, result zip, or
  private server credential.

Return a short Chinese report with:

- status: pass/fail
- blocking issues
- warnings
- suggested fixes
