# Execution Batch 001

## Title
- Active supplier-wave launch baseline freeze

## Purpose
- Freeze the current `stocklist_supplier` launch wave and rebuild the commercial launch baseline from current screening truth.

## Why this batch comes first
- We do have enough data to start the new-product phase.
- We do not yet have a safe current launch surface.
- The current screening truth is real.
- The current recommendation and approval surface is stale for this supplier wave.
- So the first job is to rebuild the baseline from the screening owner path before we review passes or near-misses.

## Scope
- In scope:
  - confirm active supplier wave
  - confirm no overlapping `F061` worker
  - freeze current raw/canonical/screening counts
  - refresh screening truth in a controlled window if needed
  - build a launch-baseline report from current row-state truth
  - explicitly flag stale derived launch surfaces
- Out of scope:
  - pass review decisions
  - user shortlist decisions
  - PO handoff release
  - post-launch monitoring

## Files expected to be touched
- `scripts/one_off/F018_build_live_price_file_launch_pack.py`
- `tests/test_f018_build_live_price_file_launch_pack.py`
- F flow files only if a root-cause fix is required for current supplier-wave freshness or state projection
- `plans/active/f-feeder-commercial-test-launch-v1/CODING_PLAN.md`
- `plans/active/f-feeder-commercial-test-launch-v1/PLAN_STATUS.md`

## Inputs
- `out/systems/F/inbox/supplier_price_list_queue_state.csv`
- `out/systems/F/inbox/suppliers/stocklist_supplier/raw_current.csv`
- `out/systems/F/inbox/suppliers/stocklist_supplier/canonical_current.csv`
- `out/systems/F/live/f_screening_row_state_live.csv`
- `out/systems/F/live/feeder_legacy_first_checks_live.csv`
- `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- `out/systems/F/live/feeder_candidate_recommendations_live.csv`
- `out/systems/F/live/feeder_approval_queue_live.csv`

## Deliverables
- `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv`
- baseline summary with:
  - active supplier id
  - active run id
  - row counts
  - freshness timestamps
  - stale-surface flags
  - launch-readiness state

## Success criteria
- the active supplier wave is explicit
- baseline counts reconcile across source, canonical, row-state, pass, and scrape-evidence surfaces
- stale recommendation and approval surfaces are flagged clearly
- the batch states whether we are ready to build pass and near-miss review packs next

## Proof required
- targeted test pass for the new baseline builder
- runtime artifact exists and matches current supplier-wave truth
- plan status updated with exact counts and next unlock condition

## Execution result
- Status:
  - completed
- `code fix applied`:
  - yes
- `isolated verification passed`:
  - yes
- `live loop verification confirmed`:
  - yes (one-off runtime artifact produced from current live supplier-wave files)

## Files changed
- `scripts/one_off/F018_build_live_price_file_launch_pack.py`
- `tests/test_f018_build_live_price_file_launch_pack.py`
- `plans/active/f-feeder-commercial-test-launch-v1/CODING_PLAN.md`
- `plans/active/f-feeder-commercial-test-launch-v1/PLAN_STATUS.md`
- `plans/active/f-feeder-commercial-test-launch-v1/EXECUTION_BATCH_001.md`

## Verification proof
- Compile:
  - `python -m py_compile scripts/one_off/F018_build_live_price_file_launch_pack.py tests/test_f018_build_live_price_file_launch_pack.py` -> pass
- Tests:
  - `pytest tests/test_f018_build_live_price_file_launch_pack.py -q` -> `1 passed`
- Runtime:
  - `python scripts/one_off/F018_build_live_price_file_launch_pack.py` -> pass

## Runtime snapshot (2026-04-22T14:32:38Z)
- Active queue:
  - `active_supplier_id=stocklist_supplier`
  - `active_run_id=stocklist_supplier_rescrape_subset_20260421T103451Z`
- Launch baseline:
  - `raw_rows=42717`
  - `canonical_rows=42663`
  - `row_state_rows_active_supplier=42856`
  - `row_state_completed_rows=9987`
  - `row_state_pending_rows=32869`
  - `row_state_pass_rows=266`
  - `row_state_timeout_rows=9721`
  - `row_state_rescan_rows=170`
- Scrape evidence:
  - `scrape_rows=4397`
  - `scrape_pass_rows=266`
  - `scrape_rescan_rows=162`
  - `scrape_fail_rows=3969`
- Derived launch-surface safety:
  - `recommendations_rows=9552`
  - `recommendations_active_supplier_rows=0`
  - `approval_rows=9552`
  - `approval_active_supplier_rows=0`
  - `derived_launch_surface_safe_flag=false`
  - `launch_readiness_state=ready_for_pass_review_with_stale_derived_surfaces`
  - `launch_readiness_reason=use_row_state_truth_for_review;do_not_trust_stale_recommendation_or_approval_surfaces`

## Deliverables produced
- `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv`
- `out/analysis_reports/f_live_price_file_launch_summary_latest.csv`

## Next batch unlock
- Batch 002 is now unblocked:
  - build pass-review and near-miss review packs from active row-state truth
  - keep stale recommendation and approval surfaces out of launch decisioning
