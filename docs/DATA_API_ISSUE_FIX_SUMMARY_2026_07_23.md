# Data API Issue Fix Summary 2026-07-23

This note summarizes the issues reported by colleagues during factor research
and the fixes applied in this release.

## Fixed In This Release

### JSON 500 On Larger Queries

Root cause:

The API returned pandas/numpy non-finite values such as `NaN`, `inf`, or
`-inf` directly in JSON records. CSV output worked because CSV serialization can
represent those values, while strict JSON responses cannot.

Fix:

`/data/query/{dataset}` now sanitizes JSON records before returning them:

```text
NaN, inf, -inf, pandas.NA -> null
```

Regression coverage:

- JSON query with 25 financial PIT rows including `inf` and `NaN` returns HTTP
  200.
- Returned JSON uses `null` for non-finite values.

### Multi-Date Valuation Queries

Root cause:

The query API only supported continuous `start_date` / `end_date` ranges.
Month-end factor workflows needed many non-contiguous valuation dates, which
forced 100+ serial requests.

Fix:

`/data/query/{dataset}` now supports explicit date lists:

```text
dates=2026-01-30,2026-02-27,2026-03-31
trade_date=2026-01-30,2026-02-27,2026-03-31
```

The filter applies to the dataset's default date column:

- `trade_date` for daily market datasets such as `valuation_1d`
- `info_date` for financial PIT datasets

Example:

```text
GET /data/query/valuation_1d?trade_date=2026-01-30,2026-02-27,2026-03-31&fields=trade_date,order_book_id,market_cap,pcf_ratio&limit=50000
```

Regression coverage:

- Query service filters explicit date lists.
- FastAPI route accepts `trade_date` and returns only requested dates.

## Operational Guidance

Large CSV extracts are still recommended for research-scale pulls. JSON is now
safe for paged queries, but CSV remains smaller and easier to load into pandas.

Suggested colleague workflow:

1. Discover schema and coverage through `/data/datasets`, `/data/coverage`, and
   `/data/schema/{dataset}`.
2. Use date filters and `order_book_id` filters whenever possible.
3. Use `trade_date`/`dates` for non-contiguous month-end snapshots.
4. Cache repeated extracts locally.

## Not Fixed In This Release

### Missing Cash-Flow Fields

`financial_pit_field_pack` still does not include operating cash flow, CapEx, or
cash-and-equivalents fields. FCF and EV factors should remain marked as proxy
calculations until a separate cash-flow/balance field pack is probed, backfilled,
QA-checked, and synced.

### 2010-2015 Historical Coverage

The current data lake is a 2016-present research lake. Extending to 2010
requires a separate backfill plan, RQData quota/range confirmation, data quality
checks, and server sync.

### Query Engine Performance

The current API still reads local Parquet files per request. Explicit date lists
reduce request count for month-end workflows, but deeper speedups require a
future DuckDB or PyArrow Dataset execution path and/or offline export jobs.
