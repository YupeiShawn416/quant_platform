# Quant Platform Current State Audit

Audit date: 2026-07-09

Latest audited commit: `79c445b add vix q5 exposure and lagged audit`

Branch: `main`

Remote: `origin https://github.com/YupeiShawn416/quant_platform.git`

## 1. Executive Summary

The project has moved beyond a single demo. It now has a working local quant
research and backtest platform MVP:

- local Parquet data lake
- DuckDB in-memory query layer
- FastAPI data and backtest API
- API token protection
- Python client
- DailyBacktestEngine V0
- Strategy Package V1 `weights` mode
- `/backtests/run` and `/backtests/run-package`
- standard result bundle generation
- current result lifecycle
- result zip download
- Dashboard MVP for current result
- research project templates
- one real strategy validation case: VIX Beta Q5 Long Only

VIX Beta Q5 should be treated as a real acceptance sample, not the product
mainline. It helped prove the package, engine, benchmark, dashboard, and audit
workflow, but the next product stage should focus on platform capability:

```text
Stage 21: Backtest Run Registry + Ephemeral Result Cache
```

The current product gap is result lifecycle management. The platform can run and
display the current result, but it does not yet have a durable run registry,
expiry-aware result cache, or multi-run browsing model.

## 2. Current Architecture

### Data Lake / Data Loader

Data is stored as local Parquet files under `data/research_data/rqdata/`, which
is ignored by Git. There is no persistent DuckDB database file. Queries use
DuckDB in-memory connections over Parquet files via `read_parquet(...)`.

Main components:

- `rq_platform.data.parquet_lake`
- `rq_platform.data.duckdb_query`
- `rq_platform.data.data_loader.ResearchDataLoader`
- `rq_platform.data_sources.rqdata_source.RQDataSource`

### Backtest Engine

`DailyBacktestEngine` is a custom daily long-only backtest engine. It loads
local stock prices, optional local index benchmark prices, optional tradability
constraints, simulates cash/positions/trades/orders, and writes a standard
result bundle.

### Strategy Package

Strategy Package V1 exists. `weights` mode is the recommended production-like
research path. It accepts `weights.csv` or `weights.parquet` with:

```text
trade_date
order_book_id
target_weight
```

`code` mode exists and can run through `BacktestJobManager`, but it is riskier
and should require Docker sandboxing in production. `signals` mode is defined in
the spec and validator mode set, but execution is not implemented.

### Result Bundle

The engine writes a standard bundle with manifest, config, summary, NAV,
account, positions, trades, orders, logs, monthly returns, rolling metrics, and
charts. Failure paths write `error.json` and `logs.txt`.

### Current Result

`CurrentBacktestStore` stores the latest result under:

```text
runs/backtests/current/
```

New API backtests clear and overwrite current. Current can be read through API,
shown in the Dashboard, deleted, and downloaded as zip.

### Dashboard

Dashboard routes under `/ui/backtests/current/*` render the current backtest:

- overview
- NAV
- account
- positions
- trades
- orders
- logs

It only supports current result. It does not yet support run selection or
multi-run comparison.

### Research Templates

The default template is `templates/research_weights_template`, which provides a
full local workflow from data loading through factor, signal, weights,
validation, and package build.

`research_factor_template` and `strategy_code_template` are useful starters but
are less complete than the weights template.

### Deployment

Deployment preparation exists:

- `deploy/systemd/quant-platform-api.service`
- `deploy/nginx/quant-platform.conf`
- `.env.production.example`
- `scripts/10_run_api_prod.py`
- `scripts/11_deploy_check.py`
- `docs/DEPLOYMENT.md`
- `docker/backtest.Dockerfile`

This is deployment preparation, not proof of a live production deployment.

## 3. Completed Capabilities

### Data

- RQData license connection code exists.
- Local Parquet data lake exists.
- DuckDB temporary query layer exists.
- 2025 A-share daily stock prices exist for `pre` and `none` adjust types.
- Index price data exists for six major indices.
- Tradability, valuation, industry classification, index components, and index
  weights exist for 2025.
- Data quality check modules exist for stock prices, index prices, tradability,
  valuation, industry, and index membership.

### API

- FastAPI service exists.
- Token auth exists. If `API_TOKEN` is unset or `change_me`, auth is bypassed
  for local development.
- Data endpoints exist:
  - `GET /health`
  - `GET /status`
  - `GET /instruments`
  - `GET /calendar`
  - `GET /prices`
  - `GET /data-quality`
- Backtest endpoints exist:
  - `GET /backtests`
  - `POST /backtests/run`
  - `POST /backtests/run-package`
  - `GET /backtests/current`
  - `GET /backtests/current/summary`
  - `GET /backtests/current/nav`
  - `GET /backtests/current/trades`
  - `GET /backtests/current/positions`
  - `GET /backtests/current/logs`
  - `GET /backtests/current/download`
  - `DELETE /backtests/current`
  - `GET /backtests/{run_id}/summary`
  - `GET /backtests/{run_id}/nav`
  - `GET /backtests/{run_id}/trades`
  - `GET /backtests/{run_id}/positions`
  - `GET /backtests/{run_id}/logs`
  - `GET /backtests/{run_id}/download`

### Backtest

- `DailyBacktestEngine V0` is implemented.
- Long-only target weights are supported.
- 100-share lot rounding is supported through configurable `lot_size`.
- Commission, tax, and slippage are supported.
- Cash shrink/partial fill behavior exists.
- `generate_weights(context, data) -> None` means no rebalance.
- Benchmark fallback warning is implemented and surfaced into summary and
  Dashboard.
- Worker CLI is available.

### Strategy Package

- Strategy Package V1 `weights` mode is real and tested.
- Package upload API is connected to `StrategyPackageJobManager`.
- `weights.csv` and `weights.parquet` are both supported.
- Long and wide weight format helpers exist.
- Zip-slip protection exists.
- Package size limit exists.
- Manifest/config validation exists.
- Requirements whitelist exists for code packages.

### Dashboard

- Dashboard MVP works for current result.
- Result zip download link exists.
- Benchmark fallback warning is visible.
- Dashboard smoke passed against the local API.

### Research Templates

- `research_weights_template` is complete enough for a default researcher flow.
- `make template-smoke` passed.
- AI-agent instructions exist in `AGENTS.md`.
- Function names are standardized:
  - `compute_factor`
  - `generate_signal`
  - `generate_weights`
  - `build_strategy_package`

### VIX Beta Q5 Pilot

- The VIX Beta Q5 Long Only pilot ran as a real Strategy Package V1 `weights`
  acceptance sample.
- It validated package build, package upload, weight execution, result bundle,
  current result, Dashboard, benchmark warning behavior, and later benchmark
  index integration.
- The Stage 20 lagged package comparison ran and showed benchmark-relative
  metrics after index prices were added.

## 4. Skeleton / Partial Capabilities

- `signals` package mode: defined, but execution is not implemented.
- `code` package mode: implemented enough for local execution, but production
  safety depends on Docker sandboxing.
- Docker runner: command builder and subprocess runner exist, but production
  image is still a template and not fully integrated into a hardened deployment.
- Docker sandbox in API: settings support `local` and `docker`; local is the
  default. Production mode is intended to use Docker but is not verified here.
- Run registry / history: not implemented as a durable registry. `/backtests`
  currently lists directories from a result store.
- Ephemeral result cache: not implemented.
- Dashboard history selection: not implemented.
- Multi-run comparison: not implemented.
- User management: not implemented.
- Simulation / paper trading: earlier simulation modules exist, but this audit
  did not verify them as current product-ready flows.
- Factor library: specification and some evaluation modules exist, but a real
  platform factor library is not complete.
- Daily ETL: partially implemented for 2025; still not a full production
  incremental pipeline across years.
- RQAlpha integration: bundle update and runner files exist historically, but
  the current product path is the custom DailyBacktestEngine V0, not real
  RQAlpha execution.

## 5. Data Layer Status

Current local datasets were checked from Parquet metadata and lightweight reads.
No RQData call or data fetch was performed.

| Dataset | Path | Rows | Columns | Date Range | IDs |
|---|---|---:|---:|---|---:|
| instruments | `data/research_data/rqdata/instruments/instruments.parquet` | 5,554 | 22 | N/A | 5,554 |
| trading_calendar | `data/research_data/rqdata/trading_calendar/trading_calendar.parquet` | 243 | 2 | 2025-01-02 to 2025-12-31 | N/A |
| prices_1d_pre | `data/research_data/rqdata/prices_1d_pre/year=2025.parquet` | 1,244,476 | 12 | 2025-01-02 to 2025-12-31 | 5,167 |
| prices_1d_none | `data/research_data/rqdata/prices_1d_none/year=2025.parquet` | 1,244,476 | 12 | 2025-01-02 to 2025-12-31 | 5,167 |
| index_prices_1d | `data/research_data/rqdata/index_prices_1d/year=2025.parquet` | 1,458 | 9 | 2025-01-02 to 2025-12-31 | 6 |
| tradability_1d | `data/research_data/rqdata/tradability_1d/year=2025.parquet` | 1,255,595 | 8 | 2025-01-02 to 2025-12-31 | 5,229 |
| valuation_1d | `data/research_data/rqdata/valuation_1d/year=2025.parquet` | 1,244,476 | 9 | 2025-01-02 to 2025-12-31 | 5,167 |
| industry_classification | `data/research_data/rqdata/industry_classification/year=2025.parquet` | 1,244,476 | 6 | 2025-01-02 to 2025-12-31 | 5,167 |
| index_components | `data/research_data/rqdata/index_components/year=2025.parquet` | 437,400 | 3 | 2025-01-02 to 2025-12-31 | 1,978 securities |
| index_weights | `data/research_data/rqdata/index_weights/year=2025.parquet` | 437,400 | 4 | 2025-01-02 to 2025-12-31 | 1,978 securities |

Index prices contain:

```text
000300.XSHG
000905.XSHG
000852.XSHG
000001.XSHG
399001.XSHE
399006.XSHE
```

Index components and weights contain:

```text
000300.XSHG
000905.XSHG
000852.XSHG
```

Stock daily update status:

- `data/research_data/rqdata/update_logs/daily_prices_2025_status.csv`
- 36 rows
- 36 success rows
- `prices_1d_pre`: 18 successful batches
- `prices_1d_none`: 18 successful batches

Quality checks currently cover:

- row counts
- date ranges
- duplicate keys
- missing close / volume fields for price data
- index coverage and missing index IDs
- tradability flags
- valuation missingness
- industry classification coverage
- index membership and weight checks

Main data layer gaps:

- Data is only 2025, not 2016-present.
- Stock daily ETL remains a 2025 MVP path.
- Daily incremental ETL exists but is not yet a fully productionized scheduler.
- No persistent DuckDB catalog, materialized views, or query cache.
- No data versioning or dataset manifest registry.
- Server-side RQData access should not be assumed without license confirmation.

## 6. Backtest Platform Status

Backtests can currently be submitted in two ways:

1. `POST /backtests/run` with JSON `strategy_code` and config.
2. `POST /backtests/run-package` with a Strategy Package zip.

Both paths produce a standard result bundle. The latest result is copied into:

```text
runs/backtests/current/
```

Current result behavior:

- New run overwrites old current.
- Current summary/nav/trades/positions/logs are available by API.
- Current can be downloaded as `current_backtest.zip`.
- Current can be deleted through API.
- Failed runs preserve `error.json` and `logs.txt`.

There is no durable run registry. `/backtests` lists result directories under
the default `BacktestResultStore`, but package jobs store results under job
directories and then copy into current. That is not enough for product-grade run
history.

Why Stage 21 is needed:

- Users need run metadata after current is overwritten.
- The platform needs to separate lightweight long-lived run records from large
  ephemeral CSV/zip artifacts.
- Dashboard/API should be able to list recent runs and show only unexpired
  cached artifacts.
- Keeping every NAV/trade/position file forever is not a good default.
- Users who need permanent full artifacts should download the result zip.

## 7. Research Workflow Status

The recommended research flow is:

1. Create a project from `research_weights_template`.
2. Edit:
   - `configs/strategy.yaml`
   - `src/strategy_research/factor.py`
   - `src/strategy_research/signal.py`
   - `src/strategy_research/portfolio.py`
3. Run template scripts from data load through validation.
4. Build a Strategy Package V1 zip.
5. Upload to `/backtests/run-package`.
6. Review the current result in Dashboard.

This keeps strategy research outside the execution engine and keeps the platform
responsible for execution, matching, cost modeling, metrics, result bundles, and
Dashboard.

Template limitations:

- Demo data is deterministic and not a real platform data API workflow.
- `research_factor_template` is a factor export starter, not a full backtest
  package workflow.
- `strategy_code_template` is a skeleton for advanced `code` mode.
- No built-in factor registry publishing flow yet.
- No standardized cloud project packaging or permissions model yet.

## 8. Deployment Status

The project has deployment preparation files but is not confirmed deployed to a
server in this audit.

Prepared:

- production runner script
- systemd unit
- nginx reverse proxy template
- production env example
- deploy check script
- deployment docs
- Docker backtest Dockerfile template

Current recommendation:

```text
local machine:
  RQData access, data ETL, data validation

server:
  API, Dashboard, Docker backtest execution, local copied data
```

For the MVP, local data collection plus `rsync` to the server is safer than
letting a cloud server directly access RQData. Server-side RQData access should
only be enabled after license and authorization are confirmed.

A lightweight cloud server can satisfy the MVP if it only serves API/Dashboard
and runs limited backtests over copied Parquet data. ECS sizing should be
increased when multi-user workloads, concurrent Docker jobs, larger history, or
multi-year datasets are introduced.

Server deployment gaps:

- No confirmed live deployment.
- HTTPS not configured in the template.
- Docker production image is not fully built from this repo.
- No process for result cache cleanup yet.
- No user isolation.
- No secrets manager.

## 9. Known Risks / Gaps

- Current-only result management is not enough; run registry/cache is needed.
- Data coverage is only 2025 and should expand to 2016-present.
- Daily ETL needs a production scheduler, retries, and dataset-level status.
- Benchmark fallback warning is implemented; missing benchmark data now marks
  benchmark metrics unreliable.
- Docker sandbox production execution is not fully validated.
- `code` mode in local execution is unsafe for untrusted strategies.
- No user management, roles, or per-user result namespace.
- No rate limiting or audit logs for API usage.
- Data authorization risk exists if RQData is accessed from cloud servers.
- Factor library is not complete.
- Simulation / paper trading is not product-ready.
- Dashboard only supports current result.
- No multi-run comparison.
- No permanent metadata registry for runs.
- No cleanup lifecycle for large result files.
- README next-step section is behind current implementation and should be
  refreshed in a later documentation pass.

## 10. Recommended Next Stage

Recommended next stage:

```text
Stage 21: Backtest Run Registry + Ephemeral Result Cache
```

Goals:

- Registry stores lightweight long-lived run metadata.
- Result Cache stores heavy artifacts such as nav/trades/positions/logs for a
  limited TTL.
- `current` continues to mean the latest selected/current run only.
- Users who need permanent full results must download result zip.
- Expired runs keep metadata but lose large cached artifacts.
- Dashboard/API can list runs and view unexpired run artifacts.

Suggested implementation shape:

- A small local registry table or JSONL/SQLite/DuckDB-backed metadata store.
- Store fields such as `run_id`, `job_id`, `strategy_name`, `mode`, `status`,
  `created_at`, `expires_at`, summary metrics, cache path, and error summary.
- Keep cache under ignored `runs/`.
- Do not store all large result files forever.
- Do not change engine semantics unless absolutely required.

## 11. Do Not Do Next

Do not make these the immediate next stage:

- Do not continue deep-diving VIX Q5 strategy logic.
- Do not build a full factor library yet.
- Do not start paper trading yet.
- Do not add a complex user system yet.
- Do not let the server directly perform large RQData pulls until authorization
  is confirmed.
- Do not permanently keep every historical NAV/trade/position artifact by
  default.

## Verification Log

Commands run:

```text
pwd
git status --short
git log --oneline -25
git branch --show-current
git remote -v
find . -maxdepth 4 -type f ... | sort
python -m pip install -e .
make test
make template-smoke
make api
make api-prod
make dashboard-smoke
```

Results:

- Initial `git status --short`: clean.
- `python -m pip install -e .`: first failed inside restricted sandbox because
  pip could not reach the package index for build dependencies; rerun with
  approved network access succeeded.
- `make test`: passed, `109 passed, 1 warning`.
- Test warning: `StarletteDeprecationWarning` from `fastapi.testclient` /
  `httpx`.
- `make template-smoke`: passed.
- `make api`: failed in restricted sandbox due reload/watch permission.
- `make api-prod`: failed in restricted sandbox due local server permission, then
  succeeded with approved local bind permission.
- `make dashboard-smoke`: failed in restricted sandbox due local connection
  permission, then passed with approved local access:
  - `/ui` 200
  - `/ui/backtests/current` 200
  - `/ui/backtests/current/overview` 200
  - `/ui/backtests/current/nav` 200
  - `/ui/backtests/current/trades` 200
  - `/ui/backtests/current/logs` 200

Explicit non-actions:

- RQData was not called.
- No new data was fetched.
- `rqalpha update-bundle` was not run.
- `.env` was not read or modified.
- No business logic or code behavior was changed.
- No `data/`, `runs/`, zip, or parquet artifact is intended for commit.
