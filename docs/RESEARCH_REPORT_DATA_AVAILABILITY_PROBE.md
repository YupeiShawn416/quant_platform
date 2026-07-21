# Research Report Data Availability Probe

This probe checks whether the current local data lake can support factors and signals commonly found in research reports.

It is a field availability audit only. It does not run a full backfill and does not build factors.

## Default Local-Only Run

```bash
make probe-research-report-data-availability
```

By default this command only reads local parquet schema and small coverage statistics. It does not call RQData.

## Optional RQData Schema Probe

```bash
make probe-research-report-data-availability ENABLE_RQDATA_PROBE=1
```

This optional mode is only for a small permission/schema probe. It must not be used as a backfill command.

## Outputs

Generated files are written under `reports/generated/` and should not be committed:

```text
reports/generated/research_report_raw_data_availability.md
reports/generated/research_report_raw_data_availability.csv
reports/generated/research_report_raw_data_availability.json
reports/generated/research_report_derived_field_dependency.md
reports/generated/research_report_derived_field_dependency.csv
reports/generated/research_report_derived_field_dependency.json
reports/generated/research_report_data_backfill_plan.md
reports/generated/research_report_data_backfill_plan.json
```

## How To Read It

`research_report_raw_data_availability.*` answers which raw, label, event, or metadata fields are already available locally, which are missing, and which may need an RQData or external-source probe.

`research_report_derived_field_dependency.*` answers which derived fields can be built from existing raw fields. Derived fields are not probed against RQData directly.

`research_report_data_backfill_plan.*` groups gaps by data pack and priority so the next data work can be scheduled without mixing raw ingestion with factor construction.

## Status Values

- `available`: local dataset and field exist.
- `derivable_from_existing`: not directly stored, but required source fields are already present.
- `available_but_latest_not_usable`: field exists but latest-date non-null coverage is zero.
- `missing`: not found in the current local lake.
- `permission_required`: optional RQData probe hit an auth or permission error.
- `not_probed`: RQData probe was not enabled.

## Priority

- `P0`: core market, valuation, PIT financial, corporate action, index, industry, and monthly panel dependencies.
- `P1`: capital flow, northbound, margin, shareholder, analyst, and event data.
- `P2`: thematic fields that may require external vendors or manual source validation.
- `P3`: high-cost or unstable fields deferred from the current roadmap.

## Do Not Commit

Do not commit `reports/generated/`, raw smoke samples, parquet files, tokens, `.env`, `data/`, `runs/`, or zip outputs.
