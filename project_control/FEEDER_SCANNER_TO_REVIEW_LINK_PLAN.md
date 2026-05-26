# Feeder Scanner To New Product Review Link Plan

## Purpose
Connect the price-list scanner to New Product Review without feeding rows too early.

The rule is:
- F061 scans supplier price-list rows.
- Nothing is delivered to New Product Review while that supplier batch is still running.
- When the supplier batch is complete, build one review pack for that supplier/run.
- The operator reviews that finished supplier pack in the UI, then can log into the supplier website and check stock/pricing against one completed list.

## Current Findings
- The scanner truth is already in F outputs:
  - `out/systems/F/inbox/supplier_price_list_run_state.csv`
  - `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/systems/F/live/feeder_legacy_first_checks_live.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
- F061 marks a supplier run complete when pending rows reach 0 in `supplier_price_list_run_state.csv`.
- The New Product Review UI already reads review-pack snapshots:
  - `out/analysis_reports/f_live_price_file_pass_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv`
  - `out/analysis_reports/f_live_price_file_review_summary_latest.csv`
- The current review pack builder is `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`.
- That builder is useful, but it currently works from broad live outputs and an older launch-baseline file. It is not yet a strict completed-supplier-batch handoff.

## Problem To Fix
Some rows can already be pushed into review-style files, but the link is loose because it is not locked to a finished supplier batch.

This creates operator problems:
- The user may see partial supplier results.
- A supplier pack may change while the user is reviewing it.
- The user cannot confidently log into the supplier website and check the completed list.
- A later scanner chunk could alter the same supplier evidence after the review pack was built.

## Target Data Flow
1. Price-list manager selects a supplier batch.
2. F061 scans that supplier batch in chunks.
3. F061 keeps updating live scanner files while the scan runs.
4. Manager waits until that supplier run is complete.
5. A new handoff builder creates an immutable review pack for that completed run.
6. New Product Review UI shows the completed supplier review pack.
7. Operator reviews passes, manual-review rows, and near misses.
8. Operator decisions continue to write to `out/systems/F/inbox/feeder_review_events.csv`.
9. Later Purchase Order logic consumes approved review decisions, not raw scanner passes.

## Completion Gate
A review pack can be built only when all of these are true:
- `supplier_price_list_run_state.run_status = completed`
- `supplier_price_list_run_state.pending_rows = 0`
- `supplier_price_list_run_state.completed_at_utc` is populated
- No pending rows remain in `supplier_price_list_active_run.csv` for that supplier/run
- F061 child process is not actively scanning that supplier/run
- Scanner evidence exists for that supplier/run in `f_screening_row_state_live.csv`

If any condition fails, the handoff state is `not_ready` and no review pack is published.

## Review Pack Contract
For each completed supplier/run, write a stable review pack:
- pass review rows
- manual-review rows
- near-miss rows
- summary metrics
- manifest

Required identity fields:
- supplier_id
- supplier_name
- run_id
- source_file_path
- source_seen_at_utc
- completed_at_utc
- candidate_id
- supplier_sku
- barcode
- asin
- title
- scan result
- review priority score

Suggested output folder:
- `out/systems/F/price_list_manager/review_handoffs/<supplier_id>/<run_id>/`

Suggested published files:
- `pass_review.csv`
- `near_miss_review.csv`
- `review_summary.csv`
- `manifest.csv`

The UI can still keep using the current latest files, but those latest files should be copied from a completed-run handoff, not built directly from an in-progress scan.

## What Should Be Fed To Review
Do feed:
- clean scanner passes that survive the existing review-pack routing
- manual-review rows that are commercially interesting
- near misses that may be worth checking

Do not feed:
- every scanner pass immediately
- incomplete supplier runs
- hard fails such as obvious no-ASIN, over-rank, hazmat, missing cost, or invalid barcode unless a later triage screen explicitly asks for them
- rows already failed by operator memory unless they are intentionally shown as known-fail memory

## UI Behavior
Price List Queue should show review handoff state:
- Running scan - review pack not ready
- Scan complete - building review pack
- Review pack ready - rows waiting in New Product Review
- Review started - decisions exist
- Review complete - no undecided review rows remain

New Product Review should show:
- supplier name
- run id or price-file date
- completed scan time
- source file/link
- clean pass count
- manual-review count
- near-miss count
- hard reject count

The operator should be able to pick a completed supplier pack, not a live moving file.

## Implementation Phases
### Phase 1 - Read-only contract check
- Add a read-only checker that decides whether the active supplier run is ready for review handoff.
- It must not write review-pack files.
- It should output a small handoff status CSV.

### Phase 2 - Completed-batch pack builder
- Adapt the current F019 logic so it can build from a specific supplier_id and run_id.
- Block if the completion gate is not true.
- Write immutable handoff files and a manifest.
- Keep existing review event memory support.

### Phase 3 - UI connection
- Make New Product Review list completed handoff packs.
- Keep the existing passes/manual-review/near-miss lanes.
- Add supplier/run/date/source visibility.
- Do not show in-progress supplier scans as review packs.

### Phase 4 - Manager hook
- After FPM130 sees a supplier scan complete, run the handoff builder once for that supplier/run.
- The build must be idempotent: rerunning it for the same completed run should not duplicate review rows or decisions.
- The manager then moves on to the next supplier.

### Phase 5 - Health and proof
- Add a health check for scanner-to-review handoff.
- Add schema checks for the handoff manifest and review files.
- Test that incomplete runs never publish.
- Test that completed runs publish exactly one review pack.
- Test that New Product Review shows the finished supplier pack.

## First Implementation Target
Entertainment Trading should be the first real proof target, but only after its current scan finishes.

Expected proof:
- Entertainment Trading run state says completed.
- Pending rows are 0.
- Review pack is built from `fpm_entertainment_trading_20260430T151417Z`.
- New Product Review shows Entertainment Trading as a completed supplier pack.
- No rows are delivered while the scan is still running.
- No Google Sheets changes.

