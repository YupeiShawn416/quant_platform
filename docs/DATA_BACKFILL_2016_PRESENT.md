# 2016-Present Data Backfill

Stage 25 prepares the local data lake for longer daily research and backtests.

The platform operating model remains:

```text
local authorized machine -> Parquet data lake -> rsync to server
```

The server should not directly access RQData by default.

## Current Limitation

Before this backfill is executed, the practical research range remains the
existing 2025 MVP data.

After the administrator completes and verifies this workflow, the supported
date range should be filled in as:

```text
SUPPORTED_DATE_RANGE=<由管理员填写>
```

Do not claim 2016-present support until the data quality report passes.

## Target Datasets

```text
instruments/instruments.parquet
trading_calendar/trading_calendar.parquet
prices_1d_pre/year=<year>.parquet
prices_1d_none/year=<year>.parquet
index_prices_1d/year=<year>.parquet
tradability_1d/year=<year>.parquet
valuation_1d/year=<year>.parquet
industry_classification/year=<year>.parquet
index_components/year=<year>.parquet
index_weights/year=<year>.parquet
```

`instruments` and `trading_calendar` are single-file datasets.

The following datasets are partitioned by year:

```text
prices_1d_pre
prices_1d_none
index_prices_1d
tradability_1d
valuation_1d
industry_classification
index_components
index_weights
```

Calendar backfill uses coverage checking plus merge and deduplication. In
normal mode it extends the existing calendar file instead of replacing covered
years. Use `--force` only when an administrator intentionally wants to rebuild
the calendar file.

## Execution Order

1. Audit current coverage.
2. Dry-run the 2016-present backfill plan.
3. Optionally run a small smoke backfill after confirming RQData usage.
4. Run the full backfill only with explicit confirmation.
5. Run data quality checks.
6. Generate server sync manifest.
7. Sync Parquet files to the server.

Before full backfill, inspect dry-run output and confirm that existing years are
shown as skipped or covered. Missing years should be shown as create or extend
work, not as an unqualified overwrite of existing data.

## Commands

Audit:

```bash
make audit-data-lake
```

Dry-run:

```bash
make backfill-core-dry-run
```

Smoke backfill:

```bash
make backfill-core-smoke
```

This can call RQData. Use it only after confirming the date range and estimated
scope.

Full backfill:

```bash
make backfill-core-full
```

The underlying CLI requires:

```text
--confirm-full-backfill
```

Direct CLI example:

```bash
PYTHONPATH=src python scripts/26_backfill_2016_present_core_data.py \
  --start-date 2016-01-01 \
  --end-date <最新交易日> \
  --datasets prices,index_prices,calendar,instruments,tradability,valuation,industry,index_members \
  --confirm-full-backfill
```

## Recovery

The workflow writes a status log under:

```text
data/research_data/rqdata/update_logs/backfill_2016_present_status.csv
```

Existing output years are skipped by default. Use `--force` only when an
administrator intentionally wants to rebuild a year.

## Quality Checks

```bash
make check-data-2016-present
```

Checks include duplicate keys, OHLC consistency, non-negative volume/turnover,
and basic cross-dataset coverage.

Reports are written under:

```text
reports/generated/
```

This directory is ignored by Git.

Backfill status snapshots are local run artifacts:

```text
reports/backfill_snapshots/
```

Do not commit them.

## Server Sync

Generate manifest:

```bash
make server-sync-manifest
```

The manifest includes the recommended `rsync` command and the dataset folders to
sync to:

```text
/opt/quant_platform/data/research_data/rqdata/
```

Do not sync `.env`, `runs/`, API tokens, license values, or sensitive logs.

## Researcher Usage

Researcher handoff documents should use:

```text
SUPPORTED_DATE_RANGE=<由管理员填写>
```

After Stage 25 is fully executed and verified, administrators can update that
placeholder for researcher trials and long-window backtests.
