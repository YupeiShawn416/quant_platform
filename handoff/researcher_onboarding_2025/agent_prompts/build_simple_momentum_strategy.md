# Agent Prompt: Build A Simple Momentum Strategy

You are helping a researcher use the Quant Platform researcher onboarding sample
project.

Goal:

```text
Build a simple 20-day momentum Top 20 equal-weight strategy package and submit it
to the platform API.
```

Rules:

- Work only inside `sample_strategy_project/`.
- Do not edit platform source code.
- Do not print or commit the API token.
- Do not upload raw market data, result zips, or generated CSV/Parquet files to
  Git.
- Use `QUANT_PLATFORM_API_URL` and `QUANT_PLATFORM_API_TOKEN` from the local
  shell environment.
- The official backtest must be run through the platform API.

Steps:

```bash
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
python scripts/07_submit_package.py
```

After the run, summarize:

- package path
- result zip path
- run_id
- total_return
- sharpe
- max_drawdown
- whether benchmark metrics are reliable
