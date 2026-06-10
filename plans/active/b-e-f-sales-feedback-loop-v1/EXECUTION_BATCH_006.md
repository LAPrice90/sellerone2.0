# Execution Batch 006

## Title
- Direct identity bridge to native summary overlap

## Job
- build a root-cause bridge that resolves F decision rows into operational truth rows without relying on replay rows.
- keep existing alignment-map and replay continuity as fallback, but prioritize direct resolved overlap.

## Allowed files to change
- `scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- `tests/test_bef002_build_sales_feedback_actuals.py`
- `tests/test_bef004_run_sales_feedback_guarded_once.py`
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_006.md`

## Expectations

### Output 1 - direct bridge truth
- consume `out/analysis_reports/hf_learning_identity_bridge_latest.csv` in `BEF002`.
- resolve direct bridge rows using strict keys:
  - `feeder_backtest_summary_live.seller_sku -> identity_bridge.supplier_sku`
  - `feeder_backtest_summary_live.asin -> identity_bridge.asin`
- do not downgrade or loosen key matching beyond the declared join rule.

### Output 2 - native overlap path
- emit a dedicated basis for direct overlap rows:
  - `actuals_basis=summary_direct_bridge`
- ensure this path is preferred over:
  - `alignment_asin_map`
  - `operational_seed_replay`
- keep fallback paths active when direct bridge rows are missing.

### Output 3 - coverage and warning clarity
- update guard metrics to report all overlap layers separately:
  - `actuals_summary_direct_bridge_rows`
  - `actuals_alignment_map_rows`
  - `actuals_seed_replay_rows`
  - `actuals_native_overlap_rows`
  - `actuals_recovered_overlap_rows`
- warning logic must remain truthful:
  - if direct bridge rows are zero, warning remains active even when fallback overlap exists.

### Output 4 - deterministic readiness
- preserve:
  - `guard_status=ready`
  - freshness integrity
- no downstream masking of unresolved identity coverage.

## Tests required
- `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py`
- `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q`
- runtime proof:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
  - second guarded rerun at `+5 minutes`

## Proof required
- show these together:
  - direct bridge overlap count:
    - `actuals_summary_direct_bridge_rows`
  - native overlap count:
    - `actuals_native_overlap_rows`
  - recovered overlap count:
    - `actuals_recovered_overlap_rows`
  - guarded decision:
    - `guard_status`
    - `readiness_label`
    - `warnings`
- success is not accepted unless direct bridge overlap is explicit in outputs.

## Success definition
- `code fix applied`:
  - direct bridge source is implemented and basis-tagged
- `isolated verification passed`:
  - compile and pytest commands pass
- `live loop verification confirmed`:
  - guarded rerun and `+5 minute` rerun both pass
- phase success threshold:
  - `actuals_summary_direct_bridge_rows > 0`
  - `guard_status=ready`
  - no freshness regression

## Timeout rule
- if `actuals_summary_direct_bridge_rows=0` after implementation:
  - park as `parked pending identity resolution feed expansion`
  - keep fallback overlap active
  - preserve explicit warning and counts

## Sign-off format
- `code fix applied: yes/no`
- `isolated verification passed: yes/no`
- `live loop verification confirmed: yes/no`

## Next step after sign-off
- expand direct bridge coverage source quality:
  - classify unresolved identity causes
  - raise direct bridge coverage without weakening join integrity

## Execution result
- completed as `implemented and runtime-stable`, but direct-bridge threshold remains unmet.
- compile:
  - `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_bef004_run_sales_feedback_guarded_once.py -q` -> pass (`10`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T09:35:46Z` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T09:41:06Z` -> pass
  - metrics unchanged from immediate post-run check
- runtime truth:
  - `guard_status=ready`
  - `readiness_label=ready_with_warnings`
  - `actuals_summary_direct_bridge_rows=0`
  - `actuals_summary_asin_rows=0`
  - `actuals_alignment_map_rows=19`
  - `actuals_native_overlap_rows=19`
  - `actuals_seed_replay_rows=38`
  - `actuals_recovered_overlap_rows=57`
  - warnings now:
    - `summary_asin_overlap_recovered_by_alignment_map`
    - `summary_direct_bridge_overlap_zero`
  - `next_action=monitor_alignment_map_and_expand_true_overlap`

## Sign-off
- `code fix applied`:
  - yes
  - strict direct identity-bridge path is implemented and basis-tagged in `BEF002`.
- `isolated verification passed`:
  - yes
  - compile and pytest passed for batch scope.
- `live loop verification confirmed`:
  - yes
  - guarded rerun plus `+5 minute` follow-up rerun both passed with stable metrics.
- phase success threshold:
  - not yet proven
  - `actuals_summary_direct_bridge_rows > 0` is still unmet in current live data.

## Follow-through - automated capture route generation
- implemented:
  - guarded run now auto-builds scope expansion artifacts when direct bridge overlap is zero:
    - `hf_scope_expansion_candidates_latest.csv`
    - `hf_scope_expansion_summary_latest.csv`
- compile:
  - `python -m py_compile scripts/one_off/BEF004_run_sales_feedback_guarded_once.py tests/test_bef004_run_sales_feedback_guarded_once.py` -> pass
- tests:
  - `pytest tests/test_bef004_run_sales_feedback_guarded_once.py tests/test_bef002_build_sales_feedback_actuals.py -q` -> pass (`12`)
- guarded rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T10:27:18Z` -> pass
- monitored follow-up check (`+5m`):
  - second `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T10:32:32Z` -> pass
  - metrics unchanged from immediate post-run check
- runtime truth:
  - `guard_status=ready`
  - `actuals_summary_direct_bridge_rows=0`
  - `scope_expansion_candidate_rows=52362`
  - `scope_expansion_outside_h_scope_rows=6979`
  - `scope_expansion_no_asin_rows=35831`
  - `scope_expansion_stale_source_rows=9552`
  - warnings now:
    - `summary_asin_overlap_recovered_by_alignment_map`
    - `summary_direct_bridge_overlap_zero`
    - `scope_expansion_candidates_ready`
  - next action now:
    - `run_scope_expansion_capture_path`

## Follow-through - capture route smoke proof
- targeted subset route:
  - dry-run:
    - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --include-alignment-missing` -> pass
  - apply:
    - `python scripts/one_off/F007_prepare_targeted_rescrape_subset.py --supplier-id stocklist_supplier --queue-source auto --include-alignment-missing --apply` -> pass
  - effect:
    - `active_supplier_rows_before=40488`
    - `active_supplier_rows_after=2207`
    - subset artifact:
      - `out/analysis_reports/f_targeted_rescrape_subset_latest.csv`
- F061 sample execution proof:
  - command:
    - `python scripts/flows/F/F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 10 --scrape-mode legacy_module`
  - result:
    - `status=success`
    - `processed_rows=10`
    - `pending_rows=2197`
    - `status_counts={"ROIFAIL":8,"RESCAN":2}`
    - `scrape_attempted_rows=2`
    - `scrape_success_rows=0`
    - `scrape_failed_rows=2`

## Follow-through - expanded capture and refresh proof
- expanded capture run:
  - command:
    - `python scripts/flows/F/F061_run_legacy_first_checks_local.py --supplier-id stocklist_supplier --max-rows 30 --scrape-mode legacy_module`
  - result:
    - `status=success`
    - `processed_rows=30`
    - `pending_rows=2167`
    - `status_counts={"ROIFAIL":20,"RESCAN":9,"OVER50K":1,"FAIL":2}`
    - `scrape_attempted_rows=11`
    - `scrape_success_rows=2`
    - `scrape_failed_rows=9`
    - `chart_daily_rows_captured=731`
- HF refresh after expanded capture:
  - `python scripts/one_off/HF000_build_learning_foundation.py` -> pass
  - `python scripts/one_off/HF001_build_learning_baseline.py` -> pass
  - `python scripts/one_off/HF002_build_learning_alignment.py` -> pass
  - key refresh truth:
    - `identity_rows=52406`
    - `identity_resolved_sku_rows=0`
    - `alignment_rows=95`
- guarded rerun after refresh:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py` at `2026-04-21T11:39:28Z` -> pass
  - monitored follow-up at `2026-04-21T11:44:50Z` -> pass
  - runtime truth:
    - `actuals_summary_direct_bridge_rows=0`
    - `scope_expansion_candidate_rows=52406`
    - `scope_expansion_outside_h_scope_rows=8828`
    - `scope_expansion_no_asin_rows=33793`
    - `scope_expansion_stale_source_rows=9785`
    - `next_action=run_scope_expansion_capture_path`
