# Execution Batch 009

## Title
- Execute sold-truth replay capture path and clear queue

## Job
- execute the guard-routed sold-truth capture action.
- remove sold-row missing-model-evidence backlog without manual row patching.

## Allowed files to change
- `scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py`
- `tests/test_bef005_run_sold_truth_replay_capture_path.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_009.md`

## Expectations

### Output 1 - capture-path runner
- provide a concrete executable for:
  - `run_sold_truth_replay_capture_path`
- runner must:
  - consume `f_sold_truth_replay_capture_queue_latest.csv`
  - run full BBP capture for queued ASINs
  - refresh post-capture alignment chain
  - rerun `F011` and `BEF004` for re-score

### Output 2 - queue reconciliation
- show before/after queue metrics:
  - `queue_rows_before`
  - `queue_rows_after`
  - `queue_rows_reduced`

### Output 3 - guard-state reconciliation
- prove warning removal:
  - `sold_truth_replay_capture_required` no longer present
- show updated guarded `next_action`.

## Tests required
- `python -m py_compile scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py tests/test_bef005_run_sold_truth_replay_capture_path.py`
- `pytest tests/test_bef005_run_sold_truth_replay_capture_path.py -q`
- runtime proof:
  - `python scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py --passes 1`

## Proof required
- show together:
  - capture queue before count
  - capture success/fail counts
  - queue after count
  - sold accuracy summary (`sold_rows_with_model_side_evidence`, `sold_rows_missing_model_side_evidence`)
  - guard next action and warnings

## Success definition
- `code fix applied`:
  - capture path exists and executes end-to-end
- `isolated verification passed`:
  - compile and pytest pass
- `live loop verification confirmed`:
  - runtime run clears sold-truth replay queue and updates guard action

## Timeout rule
- if queue remains nonzero after full queued run:
  - park as `parked pending additional sold-truth replay capture window`
  - do not claim sold-row model evidence is complete

## Execution result (2026-04-21)
- implementation status:
  - complete
- code changes applied:
  - `scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py` (added)
  - `tests/test_bef005_run_sold_truth_replay_capture_path.py` (added)
- tests:
  - compile command in this batch -> pass
  - pytest command in this batch -> pass (`2 passed`)
- runtime proof:
  - `python scripts/one_off/BEF005_run_sold_truth_replay_capture_path.py --passes 1` -> pass at `2026-04-21T12:53:18Z`
- proof metrics:
  - `queue_rows_before=38`
  - `capture_pack_rows=38`
  - `capture_success_rows=38`
  - `capture_failed_rows=0`
  - `queue_rows_after=0`
  - `queue_rows_reduced=38`
  - `queue_reduction_rate=1.0`
  - `sold_rows_with_model_side_evidence=57`
  - `sold_rows_missing_model_side_evidence=0`
  - `sold_truth_replay_queue_rows=0`
  - guard status:
    - `guard_status=ready`
    - `readiness_label=ready_with_warnings`
    - `next_action=run_scope_expansion_capture_path`
    - `sold_truth_replay_capture_required` removed
- sign-off state:
  - `code fix applied: yes`
  - `isolated verification passed: yes`
  - `live loop verification confirmed: yes`
