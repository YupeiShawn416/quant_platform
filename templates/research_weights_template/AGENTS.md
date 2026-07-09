# Agent Instructions

Do not change the project structure or standard field names.

Do not put backtest logic in this template. The platform owns execution,
matching, performance metrics, result bundles, and dashboard display.

Do not compute final performance here as a replacement for quant_platform.

Do not assume all research code must run on the server. This template is a
client-side research project. The server accepts the final Strategy Package and
acts as the unified backtest judge.

Do not commit `.env` or files generated under `data/output`.

Do not commit raw market data, API responses, result zips, or parquet outputs.
Do not paste API tokens into code or notes.

The following functions must continue to exist:

- `compute_factor`
- `generate_signal`
- `generate_weights`
- `build_strategy_package`

The final workflow must produce:

- `weights.csv`
- `weights.parquet` when `pyarrow` is available
- `strategy_package.zip`

The package must pass quant_platform `/backtests/run-package`.

Ordinary researcher onboarding should use weights mode. Code mode is an
advanced path and production use requires Docker sandboxing.

If changing the strategy, edit only `factor.py`, `signal.py`, `portfolio.py`,
and `configs/strategy.yaml` unless the user explicitly asks for a contract
change.

If a field is missing, fix the standard output. Do not bypass validators.

Any new dependency must be added to `requirements.txt` with a short reason in
the README or task notes.
