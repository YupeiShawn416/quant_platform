# Colleague Data API And Token Runbook

This runbook explains how colleagues should access the internal quant platform
data API, and how administrators should create, disable, and rotate researcher
tokens.

Do not publish this API, tokens, downloaded data, or copied Parquet files
outside the authorized internal research group.

## Server

```text
Base URL: http://39.106.218.30
Auth: X-API-Token: <researcher_token>
```

Health check does not require a token:

```bash
curl http://39.106.218.30/health
```

All `/data/*` endpoints require a token.

## Currently Open Datasets

Standard daily datasets:

```text
trading_calendar
instruments
prices_1d_pre
prices_1d_none
index_prices_1d
tradability_1d
valuation_1d
industry_classification
index_components
index_weights
```

Additional research datasets:

```text
risk_free_rate
financial_pit_field_pack
financial_cashflow_field_pack
financial_pit_quarterly
intraday_snapshots
cn_hxz_4_factors_monthly
cn_ff3_factors_monthly
hxz_monthly_research_panel
```

Important coverage notes:

- Prices and index prices currently cover complete daily price data through
  `2026-07-21`.
- Some non-price snapshots, such as valuation, tradability, industry, index
  membership, and financial PIT data, may cover `2026-07-22`.
- `intraday_snapshots` is a selected 2025 snapshot dataset, not a full realtime
  or minute-bar service.
- HXZ and FF3 outputs are experimental research datasets.

## Data Discovery

List datasets:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/datasets"
```

Get coverage:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/coverage"
```

Get schema:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/schema/financial_pit_field_pack"
```

Get cash-flow schema:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/schema/financial_cashflow_field_pack"
```

## Query Examples

Set environment variables on macOS/Linux:

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="<token_sent_securely>"
```

Fetch daily prices:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/prices_1d_pre?start_date=2026-07-13&end_date=2026-07-13&order_book_id=000001.XSHE,600519.XSHG&fields=trade_date,order_book_id,close,volume&limit=100"
```

Fetch financial PIT fields:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/financial_pit_field_pack?start_date=2026-04-01&end_date=2026-07-22&order_book_id=000001.XSHE&fields=order_book_id,report_period,info_date,revenue,net_profit,total_liabilities&limit=1000"
```

Fetch cash-flow PIT fields:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/financial_cashflow_field_pack?start_date=2026-04-01&end_date=2026-07-22&order_book_id=000001.XSHE&fields=order_book_id,report_period,info_date,net_operate_cashflow_ttm,cash_flow_from_operating_activities,cash_paid_for_asset,end_period_cash_equivalent&limit=1000"
```

Cash-flow field notes:

- `net_operate_cashflow_ttm`, `net_invest_cashflow_ttm`,
  `net_finance_cashflow_ttm`, and `net_cashflow_ttm` are RQData TTM cash-flow
  metrics normalized to snake_case API names.
- `cash_flow_from_operating_activities`,
  `cash_flow_from_investing_activities`, and
  `cash_flow_from_financing_activities` are point-in-time statement fields by
  report period and announcement date.
- `cash_paid_for_asset` is an asset-acquisition cash outflow and should be
  treated as a CapEx proxy candidate, not a fully audited canonical CapEx
  definition.
- `begin_period_cash_equivalent`, `end_period_cash_equivalent`, and
  `cash_equivalent` are available cash-equivalent fields; validate the exact
  definition before using them in EV or net-cash factors.

Fetch many month-end valuation snapshots in one request:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/valuation_1d?trade_date=2026-01-30,2026-02-27,2026-03-31&order_book_id=000001.XSHE,600519.XSHG&fields=trade_date,order_book_id,market_cap,pcf_ratio&limit=50000"
```

`dates=` is a dataset-neutral alias for the same filter. It filters the
dataset's default date column, such as `trade_date` for daily market data and
`info_date` for financial PIT data.

Fetch risk-free rate:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/risk_free_rate?start_date=2026-07-01&end_date=2026-07-14&limit=1000"
```

Fetch monthly HXZ factors:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/cn_hxz_4_factors_monthly?limit=5000"
```

Use CSV output when convenient:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/data/query/prices_1d_pre?start_date=2026-07-13&end_date=2026-07-13&fields=trade_date,order_book_id,close&format=csv" \
  -o prices_sample.csv
```

JSON output is supported for normal paged queries. The API converts missing and
non-finite numeric values such as `NaN`, `inf`, and `-inf` to JSON `null`.
CSV remains the recommended format for large extracts because it is smaller and
faster to parse into pandas.

## Python Example

```python
import os

import pandas as pd
import requests

base_url = os.environ["QUANT_PLATFORM_API_URL"]
token = os.environ["QUANT_PLATFORM_API_TOKEN"]
headers = {"X-API-Token": token}

response = requests.get(
    f"{base_url}/data/query/financial_pit_field_pack",
    params={
        "start_date": "2026-04-01",
        "end_date": "2026-07-22",
        "order_book_id": "000001.XSHE",
        "fields": "order_book_id,report_period,info_date,revenue,net_profit",
        "limit": 1000,
    },
    headers=headers,
    timeout=30,
)
response.raise_for_status()
df = pd.DataFrame(response.json()["records"])
print(df.head())
```

The single-file client examples are available in:

```text
examples/researcher_api_usage/quant_platform_client.py
examples/researcher_api_usage/data_api_quickstart.py
```

## Query Discipline

- `limit` defaults to `5000` and cannot exceed `50000`.
- Use `offset` for pagination.
- Always filter by dates, `trade_date`/`dates`, and `order_book_id` when possible.
- Do not run aggressive parallel pulls or scrape the full data lake through the
  API.
- For full-universe, long-window jobs, ask an administrator for an offline
  Parquet package or a dedicated batch export.

## Known Data Limitations

- `financial_cashflow_field_pack` includes operating/investing/financing cash
  flow fields and selected TTM metrics. FCF-style factors should still document
  whether they use `cash_paid_for_asset` as a CapEx proxy.
- `financial_pit_quarterly` is a legacy HXZ support table with limited fields;
  use `financial_pit_field_pack` for general financial statement research.
- The current core research range starts at `2016-01-04`. A 2010-2015 extension
  requires a separate backfill, QA, and data sync cycle.

## Create A Researcher Token

Run this on the server as `quant`:

```bash
cd /opt/quant_platform
source .venv/bin/activate
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py create \
  --researcher-id r003 \
  --name "Researcher Name" \
  --note "data api onboarding"
```

The plaintext token is printed once. Send it only through a secure channel.
The file stores only token hashes:

```text
config/researcher_tokens.json
```

Do not commit this file.

Restart the API after changing tokens:

```bash
sudo systemctl restart quant-platform-api
sudo systemctl status quant-platform-api --no-pager
```

## List, Disable, And Enable Tokens

List tokens without printing plaintext token values:

```bash
cd /opt/quant_platform
source .venv/bin/activate
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py list
```

Disable a token:

```bash
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py disable --researcher-id r003
sudo systemctl restart quant-platform-api
```

Re-enable a token:

```bash
PYTHONPATH=src python scripts/33_manage_researcher_tokens.py enable --researcher-id r003
sudo systemctl restart quant-platform-api
```

To rotate a token, disable the old researcher id and create a new id such as
`r003_2026q3`, or edit the config through an approved admin process.

## Security Rules

- Never share the admin `API_TOKEN`.
- Prefer one researcher token per person.
- Disable tokens when a colleague no longer needs access.
- Do not paste tokens into tickets, Git commits, notebooks, or group chats.
- Do not upload downloaded data to public repositories, public cloud drives, or
  external AI tools.
- Do not expose port `8000`; nginx should remain the public entry point.
