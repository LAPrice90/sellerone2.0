# F Cycle Backtest - Execution Batch 1

## Purpose

This file defines the next Codex execution batch.

It is not another research pass.
It is a practical work batch with:
- exact tasks
- expected files
- tests
- acceptance criteria
- proof required before sign-off

This batch is focused on stabilization and sign-off, not new architecture.

## Batch Goal

Take the current backtest from:
- operational but still carrying join-resolution WARNs

to:
- operational and deterministic
- calibration-ready
- documented enough to close the phase cleanly

## Current Starting State

Current implemented pipeline already exists:
- `scripts/flows/F/F070_build_backtest_policy_snapshot.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/one_off/F002_build_backtest_calibration_set.py`

Current health position:
- all backtest health checks are `OK`
- except `f_backtest_join_resolution = WARN`
- current WARN count is `8` rows

Current unresolved ASINs:
- `B0009OAI1S`
- `B000C214CO`
- `B005G0YQDG`
- `B09X15JF1L`

## Important Batch Rule

Do not reopen general model design in this batch.

Do not add new scoring ideas.

Only do:
- deterministic identity resolution
- calibration evidence cleanup
- guidebook / process closure

## Task 1 - Deterministic ASIN Resolution

### Goal

Remove the remaining `multi_sku_asin_match` ambiguity from the F backtest input build.

### Required implementation

Create a deterministic resolver file.

Recommended path:
- `config/f_backtest_asin_resolution.csv`

Recommended columns:
- `asin`
- `seller_sku`
- `resolution_status`
- `resolution_reason`
- `resolution_source`
- `approved_utc`

### Script changes

Update:
- `scripts/flows/F/F071_build_backtest_input_view.py`

Required behavior:
- load the resolver file if present
- when an ASIN has multiple product matches, check for a resolver entry first
- if resolver exists:
  - use the resolved `seller_sku`
  - set `mapping_status = resolved_asin_match`
- if resolver does not exist:
  - keep current `multi_sku_asin_match` behavior

### Tests to create or update

Update:
- `tests/test_f071_build_backtest_input_view.py`
- `tests/test_f074_build_backtest_health.py`

Add test coverage for:
- resolver file present and applied
- unresolved multi-SKU ASIN still becomes manual review
- health check drops join-resolution WARN when resolver covers all current ambiguous ASINs

### Test command

```powershell
pytest tests/test_f071_build_backtest_input_view.py tests/test_f074_build_backtest_health.py
```

### Acceptance criteria

- current 8 join-warning rows resolve deterministically
- `f_backtest_join_resolution` becomes `OK`
- no duplicate summary rows are introduced
- unresolved future conflicts still degrade safely to manual review

### Proof required

Show:
- resolver file contents
- post-run `feeder_backtest_health.csv`
- post-run count of rows where `mapping_status` is still `multi_sku_asin_match`

## Task 2 - Calibration Review Artifact

### Goal

Make calibration review easier and more truthful without changing the model design again.

### Required implementation

Extend calibration output so it explicitly highlights recommendation-risk mismatches.

Update:
- `scripts/one_off/F002_build_backtest_calibration_set.py`

Add fields to calibration output:
- `calibration_review_flag`
- `calibration_review_reason`
- `critical_amazon_recommendation_mismatch_flag`

### First-pass mismatch rule

Flag rows where:
- `amazon_risk_level = critical`
- and recommendation is:
  - `Normal fit`
  - `Managed fit`

This task does not have to change the scoring rule yet.
It must make the mismatch obvious for review.

### Tests to create or update

Update:
- `tests/test_f002_build_backtest_calibration_set.py`

Add test coverage for:
- critical-Amazon rows are flagged
- calibration report still builds balanced buckets
- report stays readable when some buckets are sparse

### Test command

```powershell
pytest tests/test_f002_build_backtest_calibration_set.py
```

### Acceptance criteria

- calibration report builds successfully
- mismatch rows are explicitly visible
- no change to core replay pipeline is required for this task

### Proof required

Show:
- first 20 rows of `out/analysis_reports/f_backtest_calibration_set_latest.csv`
- count of `critical_amazon_recommendation_mismatch_flag = 1`

## Task 3 - Backtest Sign-Off Guidebook

### Goal

Document the now-core process so it is recoverable and reviewable.

### Required implementation

Create one short guidebook.

Recommended path:
- `project_control/F_BACKTEST_V1_GUIDEBOOK.md`

It should cover:
- purpose of the backtest
- policy snapshot role
- input view role
- replay role
- summary role
- health file role
- identity resolution rule
- calibration workflow
- what to do when join ambiguity appears again
- what to do when calibration flags show the model is too harsh or too loose

### Tests

No automated tests required for the markdown file itself.

### Acceptance criteria

- guidebook exists
- guidebook references the real scripts and outputs
- guidebook explains the resolver rule and calibration review rule

### Proof required

Show:
- path to the new guidebook
- section list or first 40 lines

## Task 4 - Full Backtest Rerun And Evidence Pack

### Goal

Rerun the stabilized F backtest chain and capture proof.

### Run order

Run:

```powershell
python scripts/flows/F/F070_build_backtest_policy_snapshot.py
python scripts/flows/F/F071_build_backtest_input_view.py
python scripts/flows/F/F072_run_backtest_replay.py
python scripts/flows/F/F073_build_backtest_summary.py
python scripts/flows/F/F074_build_backtest_health.py
python scripts/one_off/F002_build_backtest_calibration_set.py
```

### Acceptance criteria

- policy snapshot builds
- input view builds
- replay builds
- summary builds
- health builds
- calibration set builds
- `f_backtest_join_resolution = OK`

### Proof required

Show:
- row counts from each output
- final `feeder_backtest_health.csv`
- final calibration-set path

## Batch Test Pack

Run this exact pack after code changes:

```powershell
pytest tests/test_f000_paths_and_schemas.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f002_build_backtest_calibration_set.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py
```

## Expected End State

This batch is complete when:
- join-resolution WARN is cleared
- calibration report explicitly flags recommendation mismatches
- guidebook exists
- rerun evidence is captured
- test pack passes

## Not In This Batch

Do not do these here unless a clear defect is discovered:
- new replay features
- new pricing logic
- new UI design work
- optimisation / threshold hunting
- major policy changes

## Suggested Final Output Back To User

When this batch is done, the Codex response should include:
- what changed
- which files changed
- test results
- health result summary
- whether join-resolution WARN is gone
- whether any critical-Amazon recommendation mismatches remain
