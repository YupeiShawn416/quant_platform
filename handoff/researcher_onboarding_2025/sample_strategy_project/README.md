# Sample Strategy Project

This is a minimal researcher project for the 2025 MVP trial. It builds a
Strategy Package in `weights` mode and submits it to Quant Platform.

The sample strategy is intentionally simple:

```text
20-day momentum -> top N names -> equal-weight daily target weights
```

No market data, API token, result zip, or private server address is included in
this folder.

## 1. Configure API Access

Use placeholders in docs, and set real values only in your local shell:

```bash
export QUANT_PLATFORM_API_URL="<SERVER_URL>"
export QUANT_PLATFORM_API_TOKEN="<API_TOKEN>"
```

## 2. Run The Pipeline

From this folder:

```bash
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py
```

Expected local outputs:

- `data/raw/prices.csv`
- `data/processed/factor.csv`
- `data/processed/signal.csv`
- `data/output/weights.csv`
- `package/strategy_package.zip`
- `data/output/result.zip`
- `reports/validation_report.md`

Do not commit generated data, packages, or result zips.

## 3. Researcher Rule

You may freely research factors and weights locally, but the official backtest
must be judged by the platform API.
