# Execution Batch 013

## Title
- Commercial decision bands and live-test readiness

## Job
- stop treating the system as an exact future-sales predictor.
- convert sold-truth replay evidence into business-useful outputs:
  - demand consistency
  - upper/lower sales band
  - upper/lower sales-rank band
  - starter test quantity
  - negative-mode risk
  - live-test readiness

## Why this batch exists
- the business question is:
  - is this worth testing or not
  - how much should we order to start
  - is the product getting stuck in a bad mode
- the business question is not:
  - was the forecast exactly right to the unit
- prerequisite truth from `EXECUTION_BATCH_014` and `EXECUTION_BATCH_012`:
  - sufficiency state must be explicit
  - sold decision replay must exist
  - fixed 15-SKU validation panel must be available

## Allowed files to change
- `scripts/one_off/F013_build_live_test_readiness_pack.py` (new)
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_f013_build_live_test_readiness_pack.py` (new)
- `tests/test_f011_build_sales_history_accuracy_pack.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_013.md`

## Expectations

### Output 1 - live-test readiness pack
- create `out/analysis_reports/f_live_test_readiness_pack_latest.csv`
- one row per sold product with these commercial fields:
  - `sales_lower_30d`
  - `sales_upper_30d`
  - `sales_rank_best_observed`
  - `sales_rank_worst_observed`
  - `sales_rank_stability_band`
  - `rank_snapshot_risk_state`
  - `demand_consistency_band`
  - `profit_risk_band`
  - `negative_mode_truth_state`
  - `starter_test_qty_recommended`
  - `starter_order_band`
  - `commercial_decision_state`
  - `live_test_readiness_state`

### Output 2 - commercial summary
- create `out/analysis_reports/f_live_test_readiness_summary_latest.csv`
- required summary metrics:
  - `commercial_judged_rows`
  - `false_green_rows`
  - `false_red_rows`
  - `negative_mode_miss_rows`
  - `starter_qty_too_high_rows`
  - `starter_qty_too_low_rows`
  - `band_hit_rows`
  - `live_test_ready_rows`

### Output 3 - scoring philosophy
- commercial scoring must prefer:
  - band correctness over exact-unit correctness
  - normal range over one lucky rank snapshot
  - negative-mode detection over fine forecast precision
  - safe starter quantity over aggressive full-order sizing
- first-test decisioning must be conservative:
  - use the lower sales bound, not the upper sales bound, when sizing the first test order
  - use the worse observed rank side when deciding if the product is stable enough to test
- reuse existing repo concepts where possible:
  - feeder `estimated_demand`
  - feeder `recommended_test_qty`
  - restock starter-band logic

## Tests required
- `python -m py_compile scripts/one_off/F013_build_live_test_readiness_pack.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- runtime proof:
  - `python scripts/one_off/F013_build_live_test_readiness_pack.py`
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders`

## Proof required
- show:
  - `commercial_judged_rows`
  - `false_green_rows`
  - `false_red_rows`
  - `negative_mode_miss_rows`
  - `live_test_ready_rows`
  - fixed 15-SKU panel results by class
  - guard `next_action`

## Success definition
- `code fix applied`:
  - commercial band scoring exists and no longer depends on exact unit precision as the main output.
- `isolated verification passed`:
  - compile and pytest commands pass.
- `live loop verification confirmed`:
  - sold-truth outputs now tell us whether products look worth testing and how much to start with.

## Target threshold for this batch
- minimum commercial usefulness target:
  - `commercial_judged_rows >= 40`
  - `false_green_rows` explicit
  - `negative_mode_miss_rows` explicit
  - `live_test_ready_rows` explicit
  - fixed 15-SKU panel has no blank commercial state rows

## Timeout rule
- if enough sold rows still cannot be commercially judged:
  - keep status `ready_with_warnings`
  - set status to `parked pending commercial-band source expansion`
  - record exact missing field families, not just generic coverage counts

## Non-goals
- no Google Sheets writes.
- no local DB alignment changes.
- no exact-unit prediction tuning as the primary sign-off gate.
- no pretending rank bands are proven when sold rank-window coverage is still missing.

## Execution result
- status:
  - complete (`ready_with_warnings`)
- code changes:
  - `scripts/one_off/F013_build_live_test_readiness_pack.py` added
  - `tests/test_f013_build_live_test_readiness_pack.py` added
  - `scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` updated (rank-window sufficiency now includes full-capture source)
  - `tests/test_f014_build_live_test_data_sufficiency_gate.py` updated

## Proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/F013_build_live_test_readiness_pack.py scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/BEF003_build_sales_feedback_examples.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
  - `python -m py_compile scripts/one_off/F014_build_live_test_data_sufficiency_gate.py tests/test_f014_build_live_test_data_sufficiency_gate.py` -> pass
- tests:
  - `pytest tests/test_f013_build_live_test_readiness_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_bef003_build_sales_feedback_examples.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`19`)
  - `pytest tests/test_f014_build_live_test_data_sufficiency_gate.py -q` -> pass (`3`)
- runtime:
  - `python scripts/one_off/F013_build_live_test_readiness_pack.py` at `2026-04-21T20:49:30Z` -> pass
  - `python scripts/one_off/F014_build_live_test_data_sufficiency_gate.py` at `2026-04-21T20:51:57Z` -> pass
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py --skip-builders` at `2026-04-21T20:49:37Z` -> pass

## Output truth
- commercial metrics:
  - `commercial_rows_total=57`
  - `commercial_judged_rows=57`
  - `false_green_rows=0`
  - `false_red_rows=8`
  - `negative_mode_miss_rows=0`
  - `starter_qty_too_high_rows=0`
  - `starter_qty_too_low_rows=8`
  - `band_hit_rows=23`
  - `live_test_ready_rows=2`
  - `rank_gap_rows=0`
  - `rows_using_full_capture_rank_window=57`
  - `rows_missing_rank_window=0`
- sufficiency gate state:
  - `sold_truth_state=ready_now`
  - `model_side_evidence_state=ready_now`
  - `decision_replay_state=ready_now`
  - `sales_band_data_state=ready_now`
  - `starter_qty_input_state=ready_now`
  - `rank_window_state=ready_now`
  - `sample_mix_state=ready_now`
- fixed 15-SKU panel outcomes by class:
  - `panel_rows_total=15`
  - `panel_rows_with_blank_commercial_state=0`
  - `panel_big_pass_test_buy_rows=1`
  - `panel_big_pass_watch_rows=0`
  - `panel_big_pass_reject_rows=4`
  - `panel_big_fail_test_buy_rows=0`
  - `panel_big_fail_watch_rows=0`
  - `panel_big_fail_reject_rows=5`
  - `panel_on_the_line_test_buy_rows=1`
  - `panel_on_the_line_watch_rows=0`
  - `panel_on_the_line_reject_rows=4`
- guard truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `next_action=expand_identity_bridge_resolution`

## Sign-off
- `code fix applied`: yes
- `isolated verification passed`: yes
- `live loop verification confirmed`: yes (commercial pack and sufficiency gate now both include sold-universe rank windows from full-capture evidence)
- next step condition:
  - `bounded shadow live testing is now unblocked for rows in ready_for_live_test state`
