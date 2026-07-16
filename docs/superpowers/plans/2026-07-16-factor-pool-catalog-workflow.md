# Factor Pool Catalog Workflow Implementation Plan

> **Execution rule:** implement task-by-task with RED-GREEN-REFACTOR. Do not query returns or materialize historical factor values in this slice.

**Goal:** Run the first executable slice of the approved factor-pool workflow: securely enumerate RQData fields, deterministically classify every field, and persist an auditable catalog snapshot and manifest.

**Architecture:** Add a separate `factor_pool` package beside the existing `rq_platform` package. The RQData adapter owns authentication and enumeration; pure catalog functions own normalization, hashing and classification; storage owns validated atomic persistence. Existing five-factor platform behavior and production factor-value directories remain untouched.

**Tech stack:** Python 3.13, rqdatac 3.5.x, pandas/pyarrow, PyYAML, pytest, argparse, SHA-256.

---

## Scope and acceptance boundary

This plan implements design phase A tasks 1-5 only:

1. Fix checkout-directory-name coupling in the existing test suite.
2. Add factor-pool package/configuration skeleton.
3. Probe RQData and enumerate unique field names without exposing credentials.
4. Normalize, sort, hash and classify the field catalog.
5. Persist the source catalog, quarantine view, summary and snapshot manifest atomically.

Recipe execution, preprocessing, IC screening, historical materialization and model training are explicitly deferred to later slices.

## Task 1: Remove checkout-name coupling

**Files:**

- Modify: `tests/test_imports.py`
- Test: `tests/test_imports.py`

1. Change the assertion from `PROJECT_ROOT.name == "quant_platform"` to project-marker/package-path checks.
2. Run `python -m pytest tests/test_imports.py -q` and require a pass.
3. Run a focused existing factor regression test to confirm no behavior change.

## Task 2: Add package and configuration contracts

**Files:**

- Create: `src/factor_pool/__init__.py`
- Create: `src/factor_pool/__main__.py`
- Create: `src/factor_pool/config.py`
- Create: `configs/factor_pool/catalog.yaml`
- Modify: `pyproject.toml`
- Create: `tests/factor_pool/test_config.py`

1. Write failing tests for rule-version loading, allowed roles/statuses and output-root resolution.
2. Implement typed immutable configuration objects and YAML loading.
3. Add a `rqdata` pytest marker and keep `rqdatac` an optional/lazy runtime import for offline catalog tests.
4. Re-run the focused tests.

## Task 3: Implement secure RQData capability adapter

**Files:**

- Create: `src/factor_pool/data_adapter/__init__.py`
- Create: `src/factor_pool/data_adapter/rqdata.py`
- Create: `tests/factor_pool/test_rqdata_adapter.py`
- Create: `tests/factor_pool/test_rqdata_smoke.py`

1. Write failing offline tests using a fake SDK for credential precedence, missing credential failure, authentication, enumeration normalization and secret redaction.
2. Implement credential lookup in this order: `RQDATAC_KEY`, legacy process-only `RQDATA_HTTP_TOKEN`, project `.env`; never return the secret in manifests or exceptions.
3. Implement lazy SDK import, `username="license"` authentication, capability probe and the verified SDK field-enumeration call.
4. Add an opt-in `rqdata` smoke test that skips only when no credential exists and fails on authentication/enumeration errors.

## Task 4: Implement deterministic catalog normalization and hashing

**Files:**

- Create: `src/factor_pool/catalog/__init__.py`
- Create: `src/factor_pool/catalog/normalize.py`
- Create: `tests/factor_pool/test_catalog_normalize.py`

1. Write failing tests for trimming, rejecting blanks/non-strings, stable deduplication/sort and hash determinism.
2. Define the catalog hash as SHA-256 of UTF-8 field names joined by `\n` without a terminal newline, matching the approved baseline.
3. Verify the known 13,482-field snapshot hash when the live smoke test is enabled.

## Task 5: Implement explicit-priority classification

**Files:**

- Create: `src/factor_pool/catalog/classifier.py`
- Create: `tests/factor_pool/test_catalog_classifier.py`
- Create: `tests/fixtures/factor_pool/field_names.json`

1. Derive fixture cases from live field-name shapes without storing values or credentials.
2. Write failing tests for statement-field suffixes, vendor-factor candidates, unclassified quarantine, priority conflicts and mandatory classification reasons.
3. Implement ordered rules loaded from configuration; each row must contain `field_role`, `classification_status`, `classification_reason` and `classification_rule_id`.
4. Assert raw statement fields are always `source_only`, vendor candidates are never `eligible`, and unmatched fields are always quarantined.

## Task 6: Build and atomically persist a snapshot

**Files:**

- Create: `src/factor_pool/catalog/builder.py`
- Create: `src/factor_pool/storage/__init__.py`
- Create: `src/factor_pool/storage/snapshot_store.py`
- Create: `tests/factor_pool/test_catalog_builder.py`
- Create: `tests/factor_pool/test_snapshot_store.py`

1. Write failing tests for required schema, primary-key uniqueness, counts, manifest hashes and failed-write cleanup.
2. Build a DataFrame with source metadata plus classification columns.
3. Write `source_fields.parquet`, `quarantined_fields.parquet`, `classification_summary.json` and `request_manifest.json` into a temporary directory.
4. Validate rows/schema/hash, then atomically rename into `data/1_source_cache/catalog/<snapshot_id>/`.
5. Write the non-sensitive summary manifest to `manifests/factor_pool/<snapshot_id>.json` for Git review.

## Task 7: Wire the CLI and run the real workflow

**Files:**

- Modify: `src/factor_pool/__main__.py`
- Create: `tests/factor_pool/test_cli.py`
- Runtime outputs: `data/1_source_cache/catalog/<snapshot_id>/...`
- Runtime summary: `manifests/factor_pool/<snapshot_id>.json`

1. Write failing CLI tests for `rqdata probe`, `catalog build`, `catalog validate` and `catalog summarize`.
2. Implement concise JSON-safe terminal summaries and non-zero failure exits.
3. Run the offline suite.
4. Run `python -m factor_pool rqdata probe` with the process credential.
5. Run `python -m factor_pool catalog build` and validate:
   - unique count: 13,482, unless the provider catalog changed;
   - known baseline hash: `45d11857ac9cce78946a2a7504ac6ec25cbb70c73764e45cb34ce313b4fbfbe0`, unless changed;
   - baseline classes: 9,858 / 584 / 3,040, unless changed;
   - every difference is reported, not silently accepted.

## Task 8: Regression, audit and handoff

**Files:**

- Create: `memory/2026-07-16-factor-pool-catalog-run.md`
- Modify if needed: `docs/superpowers/specs/2026-07-15-factor-pool-construction-design.md`

1. Run focused factor-pool tests and the existing platform regression suite.
2. Inspect Git diff for secrets, generated Parquet files and unrelated changes.
3. Record exact commands, SDK version, snapshot ID, counts, hashes, deviations and next slice in memory.
4. Delete temporary/interrupted output directories; retain only approved manifests and ignored runtime data.

## Stop conditions

- Missing/invalid credential: stop before creating a success manifest.
- Provider enumeration API/schema change: preserve the raw error class, create no catalog, and update adapter tests before retrying.
- Count/hash/classification drift: produce a difference report and mark the run `changed`; do not overwrite the baseline as accepted.
- Any credential fragment in logs, exceptions or diff: stop, remove the artifact and rotate the credential before continuing.
