# VIX Beta Q5 Weights Package

This directory documents the Strategy Package V1 layout for a weights-mode
strategy package. The runnable demo package is generated outside the repository:

```bash
make create-demo-weights-package
```

The command writes `/tmp/demo_weights_strategy_package.zip` with:

- `manifest.json`
- `config.json`
- `weights.csv`
- `weights.parquet`
- `README.md`

The demo uses deterministic sample target weights and does not call RQData or
fetch any new market data.
