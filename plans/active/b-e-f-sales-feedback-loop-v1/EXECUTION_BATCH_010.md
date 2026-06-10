# Execution Batch 010

## Title
- Scope-expansion capture window execution

## Job
- execute the guard-routed scope-expansion capture path.
- measure whether one bounded round improves alignment expected coverage and reduces no-source rows.

## Allowed files to change
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_010.md`

## Expectations

### Output 1 - bounded capture run
- run one bounded recovery round:
  - `HF006 -> F008 -> F009 -> HF001 -> HF002 -> HF003 -> HF005`
- round must report:
  - `pack_rows`
  - `capture_success_rows`
  - `capture_failed_rows`

### Output 2 - alignment improvement
- compare baseline vs final:
  - `no_source_rows`
  - `expected_coverage_rate`

### Output 3 - guard and sold-truth stability
- rerun:
  - `BEF004 --skip-builders`
  - `F011`
- verify:
  - `guard_status=ready`
  - `sold_truth_replay_queue_rows=0`
  - no regression of sold-row evidence coverage

## Tests required
- runtime-only batch (no code edits in runtime scripts)
- required command runs:
  - `python scripts/one_off/HF007_run_alignment_coverage_recovery.py --max-rounds 1 --batch-size 20 --passes 1 --webscrape-mode data --skip-date-scraping --only-not-in-scrape --target-coverage 0.95 --target-no-source 0`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders`
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py`

## Proof required
- baseline/final metrics from HF007 summary.
- guard and accuracy outputs after run.
- explicit statement on direct-bridge overlap threshold status.

## Success definition
- `code fix applied`: not applicable (runtime execution batch)
- `isolated verification passed`: not applicable (no code changes)
- `live loop verification confirmed`:
  - scope-expansion capture round completed and produced measurable alignment improvement

## Timeout rule
- if direct bridge overlap stays zero after round:
  - keep `ready_with_warnings`
  - escalate to identity-bridge expansion batch

## Execution result (2026-04-21)
- runtime status:
  - complete
- execution proof:
  - HF007 run -> pass
    - `pack_rows=20`
    - `capture_success_rows=20`
    - `capture_failed_rows=0`
    - `no_source_rows: 27 -> 7`
    - `expected_coverage_rate: 0.7158 -> 0.9263`
  - post-run guard -> pass
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
    - `actuals_summary_direct_bridge_rows=0`
    - `next_action=run_scope_expansion_capture_path`
  - post-run sold-truth accuracy -> pass
    - `sold_rows_with_model_side_evidence=57`
    - `sold_rows_missing_model_side_evidence=0`
    - `sold_truth_replay_queue_rows=0`
- sign-off state:
  - `live loop verification confirmed: yes`
  - direct-bridge threshold (`>0`) remains unmet
