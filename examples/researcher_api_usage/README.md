# Researcher API Usage Examples

These examples are for onboarding. They show how a researcher can fetch a small
sample from the platform API and turn it into a simple teaching weights file.

They are not platform core code and are not part of `make test`.

## Environment

```bash
export QUANT_PLATFORM_API_URL=http://127.0.0.1:8000
export QUANT_PLATFORM_API_TOKEN=<your_token>
```

If local `API_TOKEN=change_me`, the token can be omitted.

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

See `submit_package_example.md`. Do not upload API tokens, downloaded data, or
generated output files to Git.
