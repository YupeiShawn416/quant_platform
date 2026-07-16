# Factor Pool Phase A V1.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-run Phase A with auditable ingredient health, a separate control-field catalog, deterministic vendor PIT audit states, and gated `identity` pass-through recipes.

**Architecture:** Preserve the immutable 13,482-row source snapshot and add four independently validated assets beside it. Pure contract/audit functions operate on DataFrames and structured records; provider adapters only fetch and normalize data; the workflow persists each asset atomically and records rule/config hashes. No return labels, IC, model importance, or backtest results are read.

**Tech Stack:** Python 3.13, pandas, pyarrow, PyYAML, rqdatac 3.5.x, pytest, SHA-256, argparse, Git.

## Global Constraints

- Work only in the `quant_pool` Git worktree on branch `quant_pool`.
- Historical universe is the point-in-time CSI 500; never backfill current constituents.
- Ingredient observations use quarter-end signal dates from 2016-01-01 through the latest complete quarter.
- Controls never enter `factor_catalog`, IC, redundancy screening, or model features.
- PIT event tests are counterexample tests: passing yields at most `sample_alignment_passed`.
- Supplier candidates remain ineligible until a legal state transition explicitly grants eligibility.
- All runtime Parquet/cache data remains ignored; code, rules, schemas, tests, and non-sensitive manifests enter Git.
- Never print or persist a credential, credential fragment, or credential hash.
- Every implementation behavior follows RED-GREEN-REFACTOR and ends in a focused Git commit.

---

### Task 1: Versioned contracts and legal state transitions

**Files:**
- Create: `src/factor_pool/contracts/__init__.py`
- Create: `src/factor_pool/contracts/status.py`
- Create: `src/factor_pool/contracts/models.py`
- Create: `tests/factor_pool/test_contracts.py`

**Interfaces:**
- Produces: `IngredientStatus`, `PitStatus`, `FactorLifecycle`, `ControlFieldDefinition`, `AuditTransition`, and `transition_factor(current, target, reason, rule_version)`.

- [ ] **Step 1: Write failing tests** proving status values are closed, `candidate_factor → definition_verified → sample_alignment_passed` is legal, direct `candidate_factor → eligible` fails, and controls accept only `exposure_field/filter_field`.
- [ ] **Step 2: Run** `python -m pytest tests/factor_pool/test_contracts.py -q`; expect import failure for `factor_pool.contracts`.
- [ ] **Step 3: Implement immutable enums/dataclasses and an explicit transition adjacency map.** Every transition returns an audit record containing old/new state, reason, rule version and timezone-aware timestamp.
- [ ] **Step 4: Run focused tests and all `tests/factor_pool`; expect PASS.**
- [ ] **Step 5: Commit** with `git commit -m "feat: add factor pool audit contracts"`.

### Task 2: Dynamic-CSI500 ingredient health engine

**Files:**
- Create: `configs/factor_pool/ingredient_health.yaml`
- Create: `src/factor_pool/audit/__init__.py`
- Create: `src/factor_pool/audit/ingredient_health.py`
- Create: `tests/factor_pool/test_ingredient_health.py`

**Interfaces:**
- Consumes: long observations with `signal_date, order_book_id, vendor_field_name, value, industry_code, universe_member`.
- Produces: `evaluate_ingredient_health(observations, config) -> pd.DataFrame` with `first_available_date, coverage_rate, coverage_scope, usable_year_count, industry_concentration, applicable_universe, ingredient_status, quality_snapshot_id`.

- [ ] **Step 1: Write failing tests** for `preferred`, `specialized`, `sparse`, `insufficient_history`, and `pending_review`, including a bank-only field that must not be rejected for low all-market coverage.
- [ ] **Step 2: Run the focused test; expect missing module failure.**
- [ ] **Step 3: Implement deterministic aggregation.** Denominator is dynamic-member observations; usable year requires at least three observed quarters and 50% annual coverage; status priority is `insufficient_history, preferred, specialized, sparse, pending_review`.
- [ ] **Step 4: Add config validation** for dates, thresholds, quarter months, industry system and rule version; invalid overlapping thresholds fail before querying data.
- [ ] **Step 5: Run focused and factor-pool tests; expect PASS.**
- [ ] **Step 6: Commit** with `git commit -m "feat: audit factor ingredient coverage"`.

### Task 3: Independent control-field catalog

**Files:**
- Create: `configs/factor_pool/control_fields.yaml`
- Create: `src/factor_pool/catalog/control_catalog.py`
- Create: `tests/factor_pool/test_control_catalog.py`

**Interfaces:**
- Produces: `build_control_catalog(definitions, snapshot_id, created_at) -> pd.DataFrame` and `assert_controls_not_features(control_ids, feature_ids)`.
- Sources: platform datasets `industry_classification`, `valuation_1d`, `tradability_1d`, `instruments`.

- [ ] **Step 1: Write failing tests** for CITICS L1 industry, log float market cap, ST, suspension, limit-up/down, listed status and listed days; assert duplicate IDs and role leakage fail.
- [ ] **Step 2: Run the focused test; expect missing module failure.**
- [ ] **Step 3: Implement YAML loading and strict schema validation.** Every control records provider, source dataset/field, role, availability rule, definition/PIT status and version.
- [ ] **Step 4: Implement feature-leakage assertion** using set intersection and a deterministic error listing leaked IDs.
- [ ] **Step 5: Run tests; expect PASS.**
- [ ] **Step 6: Commit** with `git commit -m "feat: add independent control field catalog"`.

### Task 4: Deterministic vendor definition and PIT audit

**Files:**
- Create: `configs/factor_pool/pit_audit.yaml`
- Create: `src/factor_pool/audit/vendor_factor.py`
- Create: `tests/factor_pool/test_vendor_factor_audit.py`

**Interfaces:**
- Consumes: candidate catalog plus fixed event observations containing `factor_id, order_book_id, report_period, announcement_date, observation_date, value, expected_source_signature`.
- Produces: `audit_vendor_candidates(...) -> pd.DataFrame` with definition status, PIT status, evidence count, failure reason and audit rule version.

- [ ] **Step 1: Write failing tests** showing an announcement-day change passes only as `sample_alignment_passed`, a pre-announcement change fails, missing definition remains `pending`, and technical indicators use a separate prefix-stability check.
- [ ] **Step 2: Run the focused test; expect missing module failure.**
- [ ] **Step 3: Implement definition audit** from explicit category metadata; never infer a complete formula solely from the field name.
- [ ] **Step 4: Implement event-window counterexample evaluation.** One proven early use makes the entire candidate `failed`; no averaging can override it.
- [ ] **Step 5: Run tests; expect PASS.**
- [ ] **Step 6: Commit** with `git commit -m "feat: add deterministic vendor PIT audits"`.

### Task 5: Gated pass-through recipe contracts

**Files:**
- Create: `src/factor_pool/engine/__init__.py`
- Create: `src/factor_pool/engine/recipes.py`
- Create: `tests/factor_pool/test_recipes.py`
- Create: `recipes/vendor/.gitkeep`

**Interfaces:**
- Produces: `validate_recipe(payload, catalog) -> RecipeDefinition`, `evaluate_recipe(recipe, inputs) -> pd.Series`, and `build_vendor_passthrough(candidate) -> RecipeDefinition`.

- [ ] **Step 1: Write failing tests** for a valid single-input `identity`, rejection of arbitrary Python/eval, rejection of multiple identity inputs, rejection when definition/PIT status is below the configured gate, and exact preservation of NaN/value direction.
- [ ] **Step 2: Run the focused test; expect missing module failure.**
- [ ] **Step 3: Implement structured recipe parsing with an explicit function registry.** Initial registry includes `identity` only in this task; it invokes no dynamic code.
- [ ] **Step 4: Implement pass-through generation** with `eligible_for_model=False` regardless of audit success.
- [ ] **Step 5: Run tests; expect PASS.**
- [ ] **Step 6: Commit** with `git commit -m "feat: add gated vendor pass-through recipes"`.

### Task 6: Provider queries, caching and atomic Phase-A assets

**Files:**
- Modify: `src/factor_pool/data_adapter/rqdata.py`
- Modify: `src/factor_pool/storage/snapshot_store.py`
- Modify: `src/factor_pool/workflow.py`
- Modify: `src/factor_pool/__main__.py`
- Create: `tests/factor_pool/test_phase_a_workflow.py`

**Interfaces:**
- Produces CLI commands `audit ingredients`, `catalog controls`, `audit vendor-pit`, `recipe passthrough`, and `phase-a run`.
- Persists `ingredient_health.parquet`, `control_fields.parquet`, `vendor_factor_audit.parquet`, `quarantine_triage.parquet`, and a combined non-sensitive manifest.

- [ ] **Step 1: Write failing integration tests** with fake provider/platform adapters for chunking, cache hits, interrupted-write cleanup, asset hashes, count reconciliation and secret-free failures.
- [ ] **Step 2: Run the focused test; expect command/module failures.**
- [ ] **Step 3: Add adapter methods** for chunked factor samples and PIT financial/event metadata using only verified SDK calls; platform controls load through existing `ResearchDataLoader` contracts.
- [ ] **Step 4: Extend atomic snapshot persistence** to validate schema, primary keys, counts and SHA-256 before rename; a failed asset prevents a success manifest.
- [ ] **Step 5: Wire CLI and workflow orchestration.** Drift returns non-zero and preserves a difference report.
- [ ] **Step 6: Run factor-pool and full regression tests; expect PASS.**
- [ ] **Step 7: Commit** with `git commit -m "feat: orchestrate factor pool phase A audits"`.

### Task 7: Real re-run, acceptance report and rollback record

**Files:**
- Runtime ignored: `data/1_source_cache/catalog/<new_snapshot_id>/...`
- Create: `manifests/factor_pool/<new_snapshot_id>.json`
- Create: `docs/factor-pool-phase-a-v11-acceptance.md`
- Create: `memory/2026-07-16-factor-pool-phase-a-v11-run.md`

**Interfaces:**
- Consumes all Phase-A commands and approved V1.1 thresholds.
- Produces an acceptance decision with exact counts, hashes, coverage distributions, PIT evidence outcomes, control count, recipe count, deviations and Git commit IDs.

- [ ] **Step 1: Run offline tests** and record exact pass/fail counts.
- [ ] **Step 2: Run live RQData capability and catalog checks.** Authentication or expired license stops the run without a success manifest.
- [ ] **Step 3: Run Phase A in resumable chunks.** Never query all 9,858 fields as full-history daily data; use configured quarter-end blocks and caches.
- [ ] **Step 4: Validate invariants:** 13,482 total source fields; 9,858 statement fields; 584 vendor candidates; 3,040 quarantine inputs; zero controls in factor features; zero auto-eligible candidates.
- [ ] **Step 5: Write acceptance and memory documents** including limitations: PIT smoke is not proof, source-provider revisions remain possible, and incomplete live audits are reported as incomplete rather than fabricated.
- [ ] **Step 6: Scan Git diff and artifacts for credentials and temporary directories; remove only verified intermediate outputs.**
- [ ] **Step 7: Commit** with `git commit -m "docs: record factor pool phase A v1.1 acceptance"`.

## Rollback checkpoints

- Pre-implementation design: `b8e9d2d`.
- Original Phase-A implementation: `79ebfaa`.
- Each task above ends in a separate commit; use `git revert <commit>` for an auditable rollback instead of destructive reset.
