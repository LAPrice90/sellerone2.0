# Execution Batch 002

## Title
- Pass-review and near-miss review packs

## Purpose
- Turn the frozen `stocklist_supplier` launch baseline into user-reviewable decision surfaces.

## Why this batch comes now
- Batch 001 proved the active supplier wave is real and usable.
- It also proved the old recommendation and approval surfaces are stale for this wave.
- So Batch 002 must build review packs directly from active row-state truth and current enrichment surfaces.

## Scope
- In scope:
  - build a pass-review pack from active pass rows
  - build a near-miss review pack from reviewable completed timeout rows
  - exclude hard rejects from the review queue
  - produce summary counts and review batch counts
- Out of scope:
  - user decisions
  - shortlist approval logging
  - PO handoff release
  - post-launch monitoring

## Files touched
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `tests/test_f019_build_live_price_file_near_miss_pack.py`
- `plans/active/f-feeder-commercial-test-launch-v1/CODING_PLAN.md`
- `plans/active/f-feeder-commercial-test-launch-v1/PLAN_STATUS.md`
- `plans/active/f-feeder-commercial-test-launch-v1/EXECUTION_BATCH_002.md`

## Deliverables
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/analysis_reports/f_live_price_file_review_summary_latest.csv`

## Success criteria
- pass rows are grouped into review batches with conservative starter quantities
- reviewable near-misses are separated from hard rejects
- hard reject totals are explicit by fail code
- launch review can start without relying on stale approval surfaces

## Execution result
- Status:
  - completed
- `code fix applied`:
  - yes
- `isolated verification passed`:
  - yes
- `live loop verification confirmed`:
  - yes (one-off runtime artifacts produced from current live supplier-wave files)

## Verification proof
- Compile:
  - `python -m py_compile scripts/one_off/F019_build_live_price_file_near_miss_pack.py tests/test_f019_build_live_price_file_near_miss_pack.py` -> pass
- Tests:
  - `pytest tests/test_f019_build_live_price_file_near_miss_pack.py -q` -> `1 passed`
- Runtime:
  - `python scripts/one_off/F019_build_live_price_file_near_miss_pack.py` -> pass at `2026-04-22T14:43:41Z`

## Runtime snapshot (2026-04-22T14:43:41Z)
- Active queue:
  - `active_supplier_id=stocklist_supplier`
  - `active_run_id=stocklist_supplier_rescrape_subset_20260421T103451Z`
- Review outputs:
  - `pass_review_rows=266`
  - `near_miss_review_rows=3056`
  - `near_miss_evidence_gap_rows=2153`
  - `near_miss_commercial_rows=903`
  - `hard_reject_rows=6665`
  - `pass_review_batches=14`
  - `near_miss_review_batches=153`
- Hard reject buckets:
  - `hard_reject::OVER50K=3423`
  - `hard_reject::ROIFAIL=1936`
  - `hard_reject::NOASIN=1149`
  - `hard_reject::FAIL=152`
  - `hard_reject::HAZMATFAIL=5`

## Deliverables produced
- `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
- `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
- `out/analysis_reports/f_live_price_file_review_summary_latest.csv`

## Next batch unlock
- Batch 003 is now unblocked:
  - review pass batches first
  - review only the top near-miss batches second
  - record `test`, `watch`, or `reject`
