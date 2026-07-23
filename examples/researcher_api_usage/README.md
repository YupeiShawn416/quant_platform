# Researcher API Usage Examples

These examples are for onboarding. They show how a researcher can fetch a small
sample from the platform API and turn it into a simple teaching weights file.

They are not platform core code and are not part of `make test`.

## Environment

Server handoff:

```bash
export QUANT_PLATFORM_API_URL="http://39.106.218.30"
export QUANT_PLATFORM_API_TOKEN="<token_sent_securely>"
```

Local development:

```bash
export QUANT_PLATFORM_API_URL="http://127.0.0.1:8000"
export QUANT_PLATFORM_API_TOKEN="<your_local_token>"
```

If local `API_TOKEN=change_me`, the token can be omitted. For server use,
always pass the researcher token through `QUANT_PLATFORM_API_TOKEN`; do not put
it in scripts, notebooks, package zips, or Git-tracked files.

## Fetch Prices

Start the API first:

```bash
make api
```

Then run:

```bash
python examples/researcher_api_usage/fetch_prices_example.py
```

Output:

```text
examples/researcher_api_usage/output/prices_sample.csv
```

The `output/` directory is ignored by Git.

## Researcher Data API Client

`quant_platform_client.py` is a single-file client that can be copied into a
research project. It returns pandas DataFrames from the Stage 29 `/data/*` API.

Quickstart:

```bash
python examples/researcher_api_usage/data_api_quickstart.py
```

It fetches a trading calendar, stock prices, valuation data, builds a small
feature panel, and prints a simple example weights DataFrame.

## Build Simple Momentum Weights

After fetching prices:

```bash
python examples/researcher_api_usage/build_simple_momentum_weights.py
```

Output:

```text
examples/researcher_api_usage/output/simple_momentum_weights.csv
```

This script is only a teaching example. For real research, use
`templates/research_weights_template` and build a full Strategy Package V1 zip.

## Submit Package

See `submit_package_example.md`. For a quick server smoke from the repo root:

```bash
python scripts/18_create_demo_weights_package.py
python scripts/19_submit_demo_weights_package.py
```

The demo builder writes `/tmp/demo_weights_strategy_package.zip`; the submitter
uses `QUANT_PLATFORM_API_URL` and `QUANT_PLATFORM_API_TOKEN`, then downloads the
result bundle to `/tmp/backtest_result_demo_weights_package.zip`.

Latest verified server smoke on 2026-07-23 returned success for run
`demo_weights_package_20260723061632_5edc7e` with 36 NAV rows and 61 trades.

Do not upload API tokens, downloaded data, result bundles, or generated output
files to Git.
