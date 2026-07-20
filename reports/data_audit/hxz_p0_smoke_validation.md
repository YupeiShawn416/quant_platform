# HXZ P0 Smoke Validation

status: success

rqdata_calls: 8

## financial_factor_daily_pit

- rows: 28
- columns: ['order_book_id', 'trade_date', 'total_assets_mrq_0', 'total_assets_lyr_0', 'equity_parent_company_mrq_0', 'equity_parent_company_lyr_0', 'total_equity_mrq_0', 'net_profit_parent_company_mrq_0', 'net_profit_parent_company_lyr_0', 'adjusted_net_profit_mrq_0', 'adjusted_net_profit_lyr_0']
- duplicate_keys: 0
- null_rates: {'total_assets_mrq_0': 0.0, 'total_assets_lyr_0': 0.0, 'equity_parent_company_mrq_0': 0.0, 'equity_parent_company_lyr_0': 0.0, 'total_equity_mrq_0': 0.0, 'net_profit_parent_company_mrq_0': 0.0, 'net_profit_parent_company_lyr_0': 0.0, 'adjusted_net_profit_mrq_0': 0.25, 'adjusted_net_profit_lyr_0': 0.25}
- dtypes: {'order_book_id': 'object', 'trade_date': 'datetime64[ns]', 'total_assets_mrq_0': 'float64', 'total_assets_lyr_0': 'float64', 'equity_parent_company_mrq_0': 'float64', 'equity_parent_company_lyr_0': 'float64', 'total_equity_mrq_0': 'float64', 'net_profit_parent_company_mrq_0': 'float64', 'net_profit_parent_company_lyr_0': 'float64', 'adjusted_net_profit_mrq_0': 'float64', 'adjusted_net_profit_lyr_0': 'float64'}
- quality_issues: []

## financial_pit_quarterly

- rows: 4
- columns: ['order_book_id', 'quarter', 'info_date', 'net_profit_parent_company', 'equity_parent_company', 'rice_create_tm', 'total_equity', 'total_assets', 'if_adjusted']
- duplicate_keys: 0
- null_rates: {'info_date': 0.0, 'rice_create_tm': 0.0, 'if_adjusted': 0.0, 'total_assets': 0.0, 'equity_parent_company': 0.0, 'total_equity': 0.0, 'net_profit_parent_company': 0.0}
- dtypes: {'order_book_id': 'object', 'quarter': 'object', 'info_date': 'datetime64[ns]', 'net_profit_parent_company': 'float64', 'equity_parent_company': 'float64', 'rice_create_tm': 'datetime64[ns]', 'total_equity': 'float64', 'total_assets': 'float64', 'if_adjusted': 'int64'}
- quality_issues: []
- version_policy: {'status': 'success', 'actual_calls': 1, 'rows': 2, 'multi_version_rows': 0, 'recommended_raw_key': ['order_book_id', 'quarter', 'info_date', 'rice_create_tm', 'if_adjusted'], 'conclusion': 'retain version metadata; use latest for as-of snapshots and all for revision audit when available'}

## risk_free_rate

- rows: 7
- columns: ['trade_date', '0S', '1M', '3M', '1Y']
- duplicate_keys: 0
- null_rates: {'0S': 0.0, '1M': 0.0, '3M': 0.0, '1Y': 0.0}
- dtypes: {'trade_date': 'datetime64[ns]', '0S': 'float64', '1M': 'float64', '3M': 'float64', '1Y': 'float64'}
- unit_conclusion: decimal annual rate
- quality_issues: []

## pit_cross_validation

- status: success
- actual_calls: 4
- symbol: 600519.XSHG
- quarter: 2024q3
- info_date: 2024-10-26
- before_query_date: 2024-10-25
- after_query_date: 2024-10-26
- before_pit_rows: 0
- after_pit_rows: 1
- factor_rows: 1
- announcement_before_visible: False
- announcement_after_visible: True
- conclusion: announcement visibility validated if before_pit_rows is 0 and after_pit_rows > 0; if not, inspect non-trading day and revision behavior before production backfill
