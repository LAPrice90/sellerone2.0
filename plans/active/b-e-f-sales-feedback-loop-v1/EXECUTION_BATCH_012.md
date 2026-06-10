# Execution Batch 012

## Title
- Sold-universe decision replay and commercial bridge

## Job
- align the model to products we actually sold.
- stop treating unsold-scan overlap as the primary blocker for accuracy scoring.
- recover model decision evidence for sold ASIN rows so commercial pass/watch/reject logic can be judged on real outcomes.
- carry forward demand-band and starter-qty fields where they already exist so the next phase scores business usefulness, not exact prediction.

## Prerequisite
- `EXECUTION_BATCH_014` must run first so sufficiency status and the fixed 15-SKU validation panel are explicit before replay coding starts.

## Root-cause evidence for this batch
- `sold_rows_total=57`
- `sold_rows_with_model_side_evidence=57`
- `sold_rows_with_full_model_evidence=0`
- `decision_judged_rows=0`
- `actuals_summary_direct_bridge_rows=0`
- `direct_bridge_feasible_pair_rows=0`
- structural overlap proof:
  - `summary_asin_overlap_with_sold=0`
  - `summary_identity_pair_overlap_with_sold_asin=0`

## Allowed files to change
- `scripts/one_off/BEF006_build_sold_decision_replay_bridge.py` (new)
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef006_build_sold_decision_replay_bridge.py` (new)
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_012.md`

## Expectations

### Output 1 - sold decision replay artifact
- create `out/analysis_reports/f_sold_decision_replay_latest.csv` keyed by sold `asin`.
- required decision fields in artifact:
  - `model_decision_state`
  - `model_decision_confidence`
  - `model_expected_units_next_30d`
  - `model_expected_profit_next_30d_gbp`
  - `model_source`
  - `replay_basis`
- carry commercial guidance fields when source data exists:
  - `estimated_demand`
  - `recommended_test_qty`
  - `recommendation_status`

### Output 2 - F011 consumes replay bridge first
- update `F011` precedence so sold-row model evidence resolution is:
  1. sold decision replay bridge
  2. live summary
  3. alignment estimate fallback
- keep explicit coverage metrics:
  - `sold_rows_with_full_model_evidence`
  - `decision_judged_rows`
  - `bucket::missing_model_decision`
- preserve commercial fields needed for tolerance-band scoring in the next batch:
  - demand bucket
  - starter test qty
  - recommendation status

### Output 3 - guard routing for accuracy alignment
- add guard metric from summary output:
  - `sold_decision_replay_coverage_rows`
- routing rule:
  - if sold decision coverage is below target threshold, route to replay-coverage action.
  - do not route back to generic scope-capture loops for this condition.

## Tests required
- `python -m py_compile scripts/one_off/BEF006_build_sold_decision_replay_bridge.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- runtime proof:
  - `python scripts/one_off/BEF006_build_sold_decision_replay_bridge.py`
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders`

## Proof required
- show:
  - `sold_rows_total`
  - `sold_rows_with_full_model_evidence`
  - `decision_judged_rows`
  - `rows_with_recommended_test_qty`
  - `rows_with_demand_bucket`
  - `bucket::missing_model_decision`
  - guard `next_action`

## Success definition
- `code fix applied`:
  - sold decision replay bridge exists and is consumed by `F011`.
- `isolated verification passed`:
  - compile and pytest commands pass.
- `live loop verification confirmed`:
  - `F011` shows nonzero decision-judged sold rows and carries enough commercial fields to score demand bands and starter test qty in the next batch.

## Target threshold for this batch
- minimum recovery target:
  - `sold_rows_with_full_model_evidence >= 40`
  - `decision_judged_rows >= 40`
  - `rows_with_recommended_test_qty >= 40`

## Timeout rule
- if threshold is not met after one full replay build:
  - keep status `ready_with_warnings`
  - set status to `parked pending sold decision replay source expansion`
  - record exact missing rows and top missing-source reason codes

## Non-goals
- no Google Sheets writes.
- no local DB alignment changes.
- no extra broad unsold-product scraping as a proxy for predictor accuracy.
- no chasing exact month-unit prediction as the main business target.

## Execution proof snapshot (`2026-04-21T15:45:45Z`)

### Code changes applied
- added:
  - `scripts/one_off/BEF006_build_sold_decision_replay_bridge.py`
  - `tests/test_bef006_build_sold_decision_replay_bridge.py`
- updated:
  - `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
  - `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
  - `tests/test_f011_build_sales_history_accuracy_pack.py`
  - `tests/test_bef004_run_sales_feedback_guarded_once.py`

### Isolated verification
- compile:
  - `python -m py_compile scripts/one_off/BEF006_build_sold_decision_replay_bridge.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- pytest:
  - `pytest tests/test_bef006_build_sold_decision_replay_bridge.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`16`)

### Runtime proof
- `python scripts/one_off/BEF006_build_sold_decision_replay_bridge.py` -> pass
  - `sold_rows_total=57`
  - `sold_decision_replay_coverage_rows=57`
  - `sold_rows_with_full_model_evidence=57`
  - `rows_with_demand_bucket=57`
  - `rows_with_recommended_test_qty=57`
  - `rows_with_recommendation_status=57`
- `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` -> pass
  - `sold_rows_total=57`
  - `sold_rows_with_model_side_evidence=57`
  - `sold_rows_missing_model_side_evidence=0`
  - `sold_rows_with_full_model_evidence=57`
  - `decision_judged_rows=57`
  - `sold_decision_replay_coverage_rows=57`
  - `rows_with_demand_bucket=57`
  - `rows_with_recommended_test_qty=57`
  - `rows_with_recommendation_status=57`
  - `bucket::missing_model_decision=0`
- `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` -> pass
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `next_action=expand_identity_bridge_resolution`
  - replay-coverage warning not present because coverage threshold is met.

### Batch outcome
- `code fix applied`: yes
- `isolated verification passed`: yes
- `live loop verification confirmed`: yes
- target threshold status:
  - `sold_rows_with_full_model_evidence >= 40` -> met (`57`)
  - `decision_judged_rows >= 40` -> met (`57`)
  - `rows_with_recommended_test_qty >= 40` -> met (`57`)
