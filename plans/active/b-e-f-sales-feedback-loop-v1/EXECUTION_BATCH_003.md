# Execution Batch 003

## Title
- Guarded one-off automation gate

## Job
- run the B/E/F one-off feedback sequence in a controlled order and emit an explicit machine-readable gate decision.
- provide a single latest report that says:
  - `guard_status=ready` or `guard_status=blocked`
  - exact hard-block reasons
  - exact warnings
  - exact next action

## Allowed files to change
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- files inside `plans/active/b-e-f-sales-feedback-loop-v1/`

## Expectations

### Output 1 - guarded run report
- create:
  - `out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`
- include:
  - builder execution sequence
  - health/freshness metrics
  - actuals/review/example row counts
  - guard decision with `hard_block_reasons` and `next_action`

### Output 2 - deterministic gating
- block when freshness fail is active
- block when core outputs are empty:
  - actuals
  - review
  - examples
- surface non-blocking warnings for overlap weakness without masking root cause

## Tests required
- `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- one-off proof run:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`

## Execution result
- compile:
  - pass
- tests:
  - pass (`3`)
- one-off run:
  - pass (guard report emitted; decision blocked)

## Live proof snapshot
- `bef_sales_feedback_guarded_run_latest.json`:
  - `guard_status=blocked`
  - `hard_block_reasons=["freshness_fail_active"]`
  - `warnings=["summary_asin_overlap_zero","all_review_rows_pending_outcome","all_examples_no_operational_truth_coverage"]`
  - `next_action=refresh_ledger_then_rerun_guarded_once`
- metrics captured in guarded report:
  - `freshness_fail_count=1`
  - `freshness_lag_minutes=889.62`
  - `actuals_rows_total=58`
  - `actuals_summary_asin_rows=0`
  - `review_rows_total=266`
  - `examples_rows_total=266`

## Key finding
- guarded automation path is now implemented and deterministic.
- the block is a truthful upstream freshness block, not a downstream mask.
- overlap and pending-outcome warnings remain explicit and non-blocking relative to guard hard blocks.

## Sign-off
- `code fix applied`
- `isolated verification passed`
- `live loop verification not applicable yet`
- automation promotion status:
  - `not yet proven for schedule promotion because guard_status is blocked`

## Next step after sign-off
- promote guarded one-off execution into scheduled ownership only when guard status is consistently `ready` across proof windows
