# Research Templates

Client research templates give researchers, interns, and AI agents one stable
starting point. The goal is not to run backtests locally. The goal is to produce
standard outputs that quant_platform can validate, execute, and display.

## Templates

`research_weights_template` is the recommended default. It loads or reads data,
computes factors, creates signals, builds long-only target weights, validates
outputs, and creates a Strategy Package V1 `weights` zip.

`research_factor_template` is for factor-library preparation. It exports
`factor_long`, `factor_wide`, and a small report.

`strategy_code_template` is for advanced users who need `generate_weights` code
mode. Production code mode must use Docker sandbox execution.

## Standard Workflow

1. Create a project from a template.
2. Edit strategy logic in `factor.py`, `signal.py`, `portfolio.py`, and config.
3. Run the numbered scripts.
4. Validate outputs.
5. Build `strategy_package.zip`.
6. Upload to `/backtests/run-package`.
7. Review current results in the dashboard.

## AI Agent Workflow

Agents should keep the template structure and standard function names intact.
They should not add a custom backtest engine, rename standard columns, commit
generated data, or bypass validators.

## Standard Functions

```python
load_config(path="configs/strategy.yaml") -> dict
load_market_data(config) -> DataFrame
load_universe(config) -> DataFrame
load_benchmark(config) -> DataFrame
compute_factor(market_data, config) -> DataFrame
generate_signal(factor_df, config) -> DataFrame
generate_weights(signal_df, config) -> DataFrame
build_strategy_package(config, weights_df, output_path) -> Path
```

## Standard Fields

Factor:

```text
trade_date
order_book_id
factor_value
```

Signal:

```text
trade_date
order_book_id
signal_score
```

Weights:

```text
trade_date
order_book_id
target_weight
```

## Create A Project

```bash
PYTHONPATH=src python scripts/20_create_research_project_from_template.py \
  --template weights \
  --name my_first_factor_strategy \
  --output-dir /tmp
```

## Build A Package

```bash
cd /tmp/my_first_factor_strategy
python scripts/01_load_data.py
python scripts/02_compute_factor.py
python scripts/03_generate_signal.py
python scripts/04_generate_weights.py
python scripts/05_validate_outputs.py
python scripts/06_build_package.py
```

## Upload

Start quant_platform:

```bash
make api
```

Then from the research project:

```bash
python scripts/07_submit_package.py
```

## Future Split

The templates live in the main repository for V0 so contracts evolve beside the
platform. Once stable, they can be split into standalone starter-kit
repositories.
