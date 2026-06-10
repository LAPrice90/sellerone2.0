# Execution Batch 011

## Title
- Direct-bridge feasibility guard correction

## Job
- stop repeated `run_scope_expansion_capture_path` routing when direct bridge is structurally infeasible.
- emit explicit feasibility evidence and route to identity-resolution expansion.

## Allowed files to change
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_011.md`

## Expectations

### Output 1 - feasibility metrics
- add guarded metrics:
  - `direct_bridge_baseline_asin_rows`
  - `direct_bridge_summary_identity_pair_overlap_rows`
  - `direct_bridge_feasible_pair_rows`

### Output 2 - warning semantics
- emit `summary_direct_bridge_no_feasible_overlap` when:
  - direct bridge rows are zero
  - summary-identity overlap exists
  - feasible overlap to sold baseline is zero

### Output 3 - next action correction
- route to:
  - `expand_identity_bridge_resolution`
- do not route to:
  - `run_scope_expansion_capture_path`
  - when infeasible overlap is explicitly proven.

## Tests required
- `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- runtime proof:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders`

## Proof required
- show:
  - `actuals_summary_direct_bridge_rows`
  - `direct_bridge_baseline_asin_rows`
  - `direct_bridge_summary_identity_pair_overlap_rows`
  - `direct_bridge_feasible_pair_rows`
  - warning set
  - `next_action`

## Success definition
- `code fix applied`:
  - feasibility logic and warning/action routing added
- `isolated verification passed`:
  - compile and tests pass
- `live loop verification confirmed`:
  - runtime guarded output shows infeasible direct bridge and routes to identity resolution

## Timeout rule
- if feasible overlap remains zero after this change:
  - keep status `ready_with_warnings`
  - move implementation focus to identity-resolution feed expansion

## Execution result (2026-04-21)
- implementation status:
  - complete
- code changes applied:
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
  - `tests/test_bef004_run_sales_feedback_guarded_once.py`
- tests:
  - compile command in this batch -> pass
  - pytest command in this batch -> pass (`9 passed`)
- runtime proof:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` -> pass at `2026-04-21T14:15:03Z`
- proof metrics:
  - `actuals_summary_direct_bridge_rows=0`
  - `direct_bridge_baseline_asin_rows=57`
  - `direct_bridge_summary_identity_pair_overlap_rows=2358`
  - `direct_bridge_feasible_pair_rows=0`
  - warnings include:
    - `summary_direct_bridge_no_feasible_overlap`
  - `next_action=expand_identity_bridge_resolution`
- sign-off state:
  - `code fix applied: yes`
  - `isolated verification passed: yes`
  - `live loop verification confirmed: yes`
