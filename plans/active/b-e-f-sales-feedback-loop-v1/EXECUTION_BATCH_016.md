# Execution Batch 016

## Title
- Pass-structure reset and next-phase pass checks

## Job
- reassess the pass structure after the latest sales-truth rerun.
- plan the next phases of pass checks from the refreshed state.
- focus on false-red recovery and pass-gate clarity before widening live testing.

## Why this batch exists
- the refreshed rerun changed the pass structure again:
  - `rows_total=58`
  - `current_test_buy_rows=1`
  - `current_watch_rows=3`
  - `current_reject_rows=54`
  - `current_ready_for_live_test_rows=1`
- the main issue is now clearer:
  - many profitable rows are still blocked because the pass structure inherits `recommendation_status=reject` and `starter_test_qty_recommended=0`
  - this is producing `hold` on rows that are commercially strong enough to deserve a second-pass check
- we therefore need explicit pass-gate phases instead of one opaque pass/fail result.

## Refreshed rerun proof
- `python scripts/one_off/F011_build_sales_history_accuracy_pack.py` at `2026-04-22T13:33:05Z`
- `python scripts/one_off/F013_build_live_test_readiness_pack.py` at `2026-04-22T13:33:06Z`
- `python scripts/one_off/F016_build_stocked_sku_vetting_report.py` at `2026-04-22T13:33:09Z`

## Current pass structure

### Current `test_buy`
- `OPER::9188805646`

### Current `watch`
- `OPER::B001ET78RY`
- `OPER::B005F5TRBI`
- `OPER::B0CS3VF4GK`

### Current shape
- `false_red_rows=12`
- `false_green_rows=0`
- `starter_qty_too_high_rows=3`
- `starter_qty_too_low_rows=12`
- `live_test_ready_rows=1`

### Strong-profit rejects still blocked
- profitable rejects with `actual_profit_30d_gbp >= 20` now include:
  - `B06WW79DX5`
  - `B006PFN3BW`
  - `B002QGAF8S`
  - `B08KFFY86W`
  - `B0042SI594`
  - `B07L6H9GZ2`
  - `B000PSB13C`
  - `B086ZD7MG6`
  - `B07QQDMJ6M`
  - `B00AOES9GE`
  - `B07CN7NRF7`
  - `B093FQYQJH`
- common block pattern:
  - `recommendation_status=reject`
  - `starter_test_qty_recommended=0`
  - `starter_order_band=hold`

## Next phases of pass checks

### Phase 20 - pass-gate decomposition
- build an explicit blocker report for every sold row.
- required blocker buckets:
  - `blocked_profit_floor`
  - `blocked_negative_mode`
  - `blocked_rank_risk`
  - `blocked_demand_instability`
  - `blocked_legacy_recommendation_reject`
  - `blocked_zero_starter_qty`
  - `blocked_missing_model_decision`
- success condition:
  - every `watch` and `reject` row has a named first blocker
  - profitable rejects are separated from true commercial fails

### Phase 21 - false-red recovery lane
- create a second-pass review lane for rows that are:
  - `profit_risk_band` in `healthy|strong`
  - `negative_mode_truth_state=negative_mode_clear`
  - `rank_snapshot_risk_state` in `low_rank_risk|moderate_rank_risk`
  - currently blocked only by legacy recommendation or zero starter qty
- output classes:
  - `promote_to_test_buy`
  - `promote_to_watch`
  - `keep_reject`
- success condition:
  - the profitable reject set gets a clear promote/hold decision instead of one generic reject

### Phase 22 - pass panel expansion
- expand manual validation beyond the fixed 15-row panel to include:
  - all current `test_buy` rows
  - all current `watch` rows
  - all profitable rejects above `GBP20`
  - near-floor rows around `GBP15` to `GBP25`
- success condition:
  - we can see whether the second-pass lane is recovering real winners without letting obvious losers through

### Phase 23 - staged shadow-live checks
- run checks in tiers, not one release bucket:
  - Tier A: current `test_buy`
  - Tier B: promoted `watch`
  - Tier C: review-only profitable rejects
- verify:
  - pass count
  - starter quantity sanity
  - rank stability
  - negative-mode avoidance
- success condition:
  - live testing expands only after the pass-gate decomposition and false-red recovery are explicit

## Non-goals
- no Google Sheets writes
- no local DB manual alignment
- no threshold masking to manufacture passes
- no promoting rows with active negative-mode or weak profit

## Success definition
- we move from one opaque pass result to staged pass checks with explicit blocker reasons.
- false-red recovery becomes measurable.
- next live-test expansion uses named lanes instead of generic reject/pass outputs.

## Execution result
- status:
  - complete (`ready_with_warnings`)
- code changes:
  - `scripts/one_off/F017_build_pass_gate_review_pack.py` added
  - `tests/test_f017_build_pass_gate_review_pack.py` added

## Proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/F017_build_pass_gate_review_pack.py tests/test_f017_build_pass_gate_review_pack.py` -> pass
- tests:
  - `pytest tests/test_f017_build_pass_gate_review_pack.py -q` -> pass (`1`)
- runtime:
  - `python scripts/one_off/F017_build_pass_gate_review_pack.py` at `2026-04-22T13:41:57Z` -> pass

## Output truth
- review pack:
  - `rows_total=58`
  - `current_test_buy_rows=1`
  - `current_watch_rows=3`
  - `profitable_reject_rows=12`
  - `false_red_candidate_rows=6`
  - `promote_to_test_buy_rows=2`
  - `promote_to_watch_rows=4`
  - `review_only_profitable_reject_rows=6`
  - `keep_reject_rows=42`
- staged tiers:
  - `tier_a_rows=3`
  - `tier_b_rows=7`
  - `tier_c_rows=6`
  - `tier_d_rows=42`
- blocker counts:
  - `blocker::blocked_missing_model_decision=3`
  - `blocker::blocked_negative_mode=3`
  - `blocker::blocked_profit_floor=44`
  - `blocker::blocked_rank_risk=6`
  - `blocker::blocked_demand_instability=38`
  - `blocker::blocked_legacy_recommendation_reject=51`
  - `blocker::blocked_zero_starter_qty=51`
- profitable rows promoted by second pass:
  - `promote_to_test_buy`:
    - `B06WW79DX5`
    - `B006PFN3BW`
  - `promote_to_watch`:
    - `B002QGAF8S`
    - `B07CN7NRF7`
    - `B07L6H9GZ2`
    - `B086ZD7MG6`
  - `review_only_profitable_reject`:
    - `B000PSB13C`
    - `B0042SI594`
    - `B00AOES9GE`
    - `B07QQDMJ6M`
    - `B08KFFY86W`
    - `B093FQYQJH`
- expanded pass panel:
  - `expanded_panel_rows_total=18`
  - `expanded_panel::current_test_buy=1`
  - `expanded_panel::current_watch=3`
  - `expanded_panel::profitable_reject_gbp20_plus=12`
  - `expanded_panel::near_floor_review=2`

## Sign-off
- `code fix applied`: yes
- `isolated verification passed`: yes
- `live loop verification confirmed`: yes
- next step condition:
  - use the new review pack to decide whether the promoted `tier_a` and `tier_b` rows should be accepted into the live-test lane without changing the original commercial pack yet
