# Financial PIT Field Pack

This workflow expands the local financial point-in-time field coverage without changing the existing `financial_pit_quarterly` dataset.

## Purpose

Research reports often use balance-sheet and income-statement fields beyond the original HXZ minimum set. This field pack stores only fields verified by the Stage 33B P0 RQData probe.

## Source

Fields come from `rqdatac.get_pit_financials_ex` and are selected from:

```text
reports/generated/research_report_p0_rqdata_probe.csv
```

Only rows with:

```text
data_pack == financial_pit_core
rqdata_probe_status == available
```

are eligible.

## PIT Rule

Rows must keep `info_date` as the PIT availability date. `report_period` alone is not sufficient and must not be used as the data availability date.

## Dataset

```text
data/research_data/rqdata/financial_pit_field_pack/
```

The current writer partitions by `info_date` year:

```text
financial_pit_field_pack/year=2025/financial_pit_field_pack.parquet
```

## Commands

Dry-run plan:

```bash
make backfill-financial-pit-field-pack START_DATE=2024-01-01 END_DATE=2025-12-31
```

Smoke with the fixed six-stock sample:

```bash
make financial-pit-field-pack-smoke START_DATE=2024-01-01 END_DATE=2025-12-31
```

Quality and coverage:

```bash
make check-financial-pit-field-pack
make audit-financial-pit-field-pack
```

Full historical runs should be split by period after smoke approval:

```text
2016-2018
2019-2021
2022-2024
2025-2026
```

## Quality Checks

Checks include:

- duplicate `order_book_id + report_period + info_date`
- parseable `info_date`
- parseable `report_period`
- non-empty numeric coverage per field
- PIT guard: `info_date` must not precede report-period end
- reconciliation with existing `financial_pit_quarterly` where fields overlap

## Existing Dataset Relationship

`financial_pit_quarterly` remains unchanged. This workflow writes a separate extension table and reports any overlapping-field comparison instead of overwriting old data.

## Limits

This stage does not backfill unavailable fields, corporate actions, valuation fields, index universes, capital flow, or derived factors. Generated data and reports under `data/` and `reports/generated/` are not committed.
