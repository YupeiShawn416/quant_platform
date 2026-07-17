# Intraday Snapshot Data

Stage 32A adds a small intraday snapshot dataset for A-share timing research.
It is not a full minute-bar data lake.

## Scope

Fixed snapshot points:

```text
09:45
09:55
10:00
14:30
14:45
14:55
```

The first smoke range is:

```text
2025-01-01 to 2025-01-10
```

The first planned backfill range is:

```text
2025-01-01 to 2026-07-13
```

Only `adjust_type="none"` is used for minute close prices.

## Dataset

```text
data/research_data/rqdata/intraday_snapshots/
├── year=2025/
│   ├── month=01.parquet
│   └── ...
└── year=2026/
    └── month=07.parquet
```

Columns:

```text
trade_date
datetime
snapshot_time
order_book_id
close
volume
total_turnover
```

`volume` and `total_turnover` may be null if the provider does not return them
for minute bars. The quality report will surface that as a warning.

## Dry Run

Default behavior is dry-run unless the explicit confirmation flag is present:

```bash
PYTHONPATH=src python scripts/43_backfill_intraday_snapshots.py \
  --start-date 2025-01-01 \
  --end-date 2025-01-10 \
  --dry-run
```

## Smoke

This may call RQData and should only be run on the local authorized machine:

```bash
make intraday-snapshot-smoke START_DATE=2025-01-01 END_DATE=2025-01-10
```

If minute permission, quota, DNS, or field issues occur, stop and report the
error before expanding the range.

## Quality And Coverage

```bash
make check-intraday-snapshots
make audit-intraday-snapshots
```

Reports:

```text
reports/generated/intraday_snapshot_quality.md
reports/generated/intraday_snapshot_quality.json
reports/generated/intraday_snapshot_coverage.md
reports/generated/intraday_snapshot_coverage.json
```

Quality checks include:

- duplicate `trade_date + snapshot_time + order_book_id`
- `close > 0`
- `volume >= 0`
- `total_turnover >= 0` when present
- no snapshot times outside the fixed six points
- core points `09:55` and `10:00`
- low symbol coverage warnings
- status log rows with `success` and `row_count=0`

## Do Not Commit

Do not commit:

```text
data/
runs/
*.parquet
*.zip
reports/generated/
.env
config/researcher_tokens.json
```
