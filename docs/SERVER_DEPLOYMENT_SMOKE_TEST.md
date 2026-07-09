# Server Deployment Smoke Test

## 1. Local Variables

Run these from your local machine:

```bash
export QUANT_PLATFORM_API_URL=http://SERVER_IP
export QUANT_PLATFORM_API_TOKEN=<your_token>
```

Do not commit real token values.

## 2. Health Check

```bash
curl "$QUANT_PLATFORM_API_URL/health"
```

Expected: JSON with `status=ok`.

## 3. Status Check

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/status"
```

Expected: key 2025 datasets exist and have non-zero rows.

## 4. Small Data Query

The actual `/prices` endpoint parameters are `symbols`, `start`, `end`,
`adjust_type`, and `fields`.

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/prices?symbols=000001.XSHE,600519.XSHG&start=2025-01-02&end=2025-01-10&adjust_type=pre&fields=open,close,volume"
```

Expected: JSON with a positive `count`.

## 5. Python Client Check

```bash
python - <<'PY'
import os
from rq_platform.client import QuantPlatformClient

client = QuantPlatformClient(
    base_url=os.environ["QUANT_PLATFORM_API_URL"],
    token=os.environ.get("QUANT_PLATFORM_API_TOKEN"),
)
print(client.health())
print(client.status()["datasets"].keys())
df = client.get_prices(
    symbols=["000001.XSHE", "600519.XSHG"],
    start="2025-01-02",
    end="2025-01-10",
    adjust_type="pre",
    fields=["open", "close", "volume"],
)
print(df.head())
print("rows", len(df))
PY
```

## 6. Dashboard Check

Open:

```text
http://SERVER_IP/ui/backtests/current
```

If there is no current result yet, the page may show an empty state. That is
acceptable before a package backtest has run.

## 7. Demo Package Backtest

Build a demo package locally:

```bash
make create-demo-weights-package
```

Upload it:

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  -F "file=@/tmp/demo_weights_strategy_package.zip" \
  "$QUANT_PLATFORM_API_URL/backtests/run-package"
```

If the package path differs, use the path printed by the command.

## 8. Result Check

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/current/summary"
```

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/current/nav"
```

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/current/trades"
```

```bash
curl -H "X-API-Token: $QUANT_PLATFORM_API_TOKEN" \
  "$QUANT_PLATFORM_API_URL/backtests/current/download" \
  -o /tmp/current_backtest.zip
```

Do not commit downloaded result zips.

## 9. Failure Checklist

- `401`: token is missing or wrong.
- `502`: nginx cannot reach Uvicorn.
- systemd service is not running.
- Port 8000 is exposed or blocked incorrectly.
- `DATA_ROOT` points to the wrong directory.
- Parquet files were not synced.
- `client_max_body_size` is too small for uploaded packages.
- Docker permission is missing for `quant`.
- Docker image was not built.
- `BACKTEST_EXECUTION_MODE=docker` but Docker runner/image is not ready.
