# Researcher Data API

Stage 29 adds a small read-only data API for researchers. Researchers use their
own API token to fetch standard platform data for local research and strategy
package generation.

Supported date range:

```text
2016-01-04 to 2026-07-10
```

## Token

Pass the token in the request header:

```bash
curl -H "X-API-Token: <your_token>" http://127.0.0.1:8000/data/datasets
```

Local development can omit the token when `API_TOKEN=change_me`.

## Datasets

- `trading_calendar`
- `instruments`
- `prices_1d_pre`
- `prices_1d_none`
- `index_prices_1d`
- `tradability_1d`
- `valuation_1d`
- `industry_classification`
- `index_components`
- `index_weights`

## Endpoints

```text
GET /data/datasets
GET /data/coverage
GET /data/schema/{dataset}
GET /data/query/{dataset}
```

Query parameters:

```text
start_date=2025-01-02
end_date=2025-01-31
order_book_id=000001.XSHE,600519.XSHG
fields=trade_date,order_book_id,close
limit=5000
offset=0
format=json
```

`limit` defaults to `5000` and cannot exceed `50000`. Use `offset` to page
through larger result sets. Do not pull the entire data lake.

CSV output:

```text
GET /data/query/prices_1d_pre?...&format=csv
```

## Python Client

Copy or import:

```text
examples/researcher_api_usage/quant_platform_client.py
```

Example:

```python
from quant_platform_client import QuantPlatformClient

client = QuantPlatformClient("http://127.0.0.1:8000", "<your_token>")
prices = client.get_prices(
    "2025-01-02",
    "2025-01-31",
    order_book_ids=["000001.XSHE", "600519.XSHG"],
    fields=["trade_date", "order_book_id", "close"],
)
```

Quickstart:

```bash
export QUANT_PLATFORM_API_URL=http://127.0.0.1:8000
export QUANT_PLATFORM_API_TOKEN=<your_token>
python examples/researcher_api_usage/data_api_quickstart.py
```

Researchers do not need RQData or SSH access. The server exposes only the
standard API surface, not the server filesystem.
