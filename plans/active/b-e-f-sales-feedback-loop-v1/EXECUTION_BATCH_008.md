# Execution Batch 008

## Title
- Sold-truth replay capture queue and guarded next-action wiring

## Job
- turn missing sold-row model evidence into an explicit automated capture queue.
- make guarded outputs route to sold-truth capture before further quality scoring claims.

## Allowed files to change
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_008.md`

## Expectations

### Output 1 - sold-truth replay queue
- emit `f_sold_truth_replay_capture_queue_latest.csv` from `F011`.
- queue rows are sold ASINs where model-side evidence is missing.
- each queue row must include:
  - `asin`
  - `amazon_link`
  - `seller_sku`
  - explicit `capture_reason`

### Output 2 - summary metric wiring
- add `sold_truth_replay_queue_rows` to `f_sales_history_accuracy_summary_latest.csv`.
- count must reconcile with queue file row count.

### Output 3 - guarded action routing
- in `BEF004` emit:
  - `metrics.sold_truth_replay_queue_rows`
  - warning `sold_truth_replay_capture_required` when queue rows > 0
  - `next_action=run_sold_truth_replay_capture_path` when the warning is active

## Tests required
- `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`

## Proof required
- show together:
  - `sold_rows_total`
  - `sold_rows_missing_model_side_evidence`
  - `sold_truth_replay_queue_rows`
  - queue csv row count
  - guard warning set includes `sold_truth_replay_capture_required`
  - guard `next_action`

## Success definition
- `code fix applied`:
  - queue and guard wiring added
- `isolated verification passed`:
  - compile and pytest pass
- `live loop verification confirmed`:
  - `F011` and `BEF004` runtime proofs write expected metrics and warnings

## Timeout rule
- if queue rows remain nonzero:
  - park as `parked pending sold-truth replay capture execution`
  - keep sold-truth queue as blocking evidence for decision-coverage claims

## Execution result (2026-04-21)
- implementation status:
  - complete with warning state
- code changes applied:
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
  - `tests/test_f011_build_sales_history_accuracy_pack.py`
  - `tests/test_bef004_run_sales_feedback_guarded_once.py`
- tests:
  - compile command in this batch -> pass
  - pytest command in this batch -> pass (`11 passed`)
- runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` -> pass at `2026-04-21T12:43:24Z`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` -> pass at `2026-04-21T12:43:30Z`
- proof metrics:
  - `sold_rows_total=57`
  - `sold_rows_missing_model_side_evidence=38`
  - `sold_truth_replay_queue_rows=38`
  - queue csv:
    - `out/analysis_reports/f_sold_truth_replay_capture_queue_latest.csv`
  - guard warning set includes:
    - `sold_truth_replay_capture_required`
  - guard `next_action`:
    - `run_sold_truth_replay_capture_path`
- sign-off state:
  - `code fix applied: yes`
  - `isolated verification passed: yes`
  - `live loop verification confirmed: yes`
- timeout-rule disposition:
  - `parked pending sold-truth replay capture execution`
