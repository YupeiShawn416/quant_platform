# Daily Data Update

Stage 26 adds a local daily after-market update workflow for the Parquet data
lake.

Current supported date range:

```text
SUPPORTED_DATE_RANGE=2016-01-04 to 2026-07-10
```

## Scope

Daily update extends the existing local data lake after the full backfill has
been completed and verified.

Default datasets:

```text
calendar
instruments
index_prices
prices
tradability
valuation
industry
index_members
```

`calendar` and `instruments` are single-file datasets. Prices, index prices,
tradability, valuation, industry, index components, and index weights are
year-partitioned datasets.

This workflow does not provide realtime data, minute bars, or paper trading.
Those are separate product surfaces and are intentionally out of scope here.

## Dry Run

Dry-run does not call RQData. Coverage is determined from actual Parquet
`trade_date` max dates, not only from the status log.

```bash
make daily-update-dry-run END_DATE=2026-07-11
```

If every selected dataset already covers the target date, the plan returns
no-op. If the status log says success but the Parquet files have not advanced,
the plan marks the dataset as `repair_needed` or `update_needed`.

## Real Update

Real update requires explicit confirmation:

```bash
make daily-update END_DATE=2026-07-11
```

The underlying command uses:

```text
--confirm-daily-update
```

Do not run a real update until the dry-run plan has been inspected.

## Quality Check

After a real update, run:

```bash
make check-data-2016-present
make daily-update-status
```

The update report is written to:

```text
reports/generated/daily_update_report.md
reports/generated/daily_update_report.json
```

If quality issues are present, treat the update as failed.

Daily update also reconciles status logs with actual Parquet coverage:

```bash
make reconcile-daily-update
```

Core datasets must not report `success` with `row_count=0` on a non-empty
trading date range. Such rows are treated as suspect and block server sync.

## Server Sync

Only sync after the daily update, reconciliation, and quality checks pass.

Generate the sync manifest:

```bash
make server-sync-manifest
```

Then use the administrator-approved rsync command from the manifest.
Do not rsync when `recommend_rsync=false`, any core dataset has a coverage
mismatch, or any core dataset has `success` with `row_count=0`.

## Recovery

Daily update writes a status log:

```text
data/research_data/rqdata/update_logs/daily_update_status.csv
```

If a dataset fails, inspect the status log and rerun only after understanding
the failed date range. Use `--force` only when an administrator intentionally
wants to rebuild or refresh the affected range.

## Do Not Commit

Do not commit:

```text
.env
data/
runs/
*.zip
*.parquet
reports/generated/
reports/backfill_snapshots/
__pycache__/
*.egg-info/
.venv/
```
