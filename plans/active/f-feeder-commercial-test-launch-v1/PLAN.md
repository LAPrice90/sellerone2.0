# Plan

## Goal
- Final outcome:
  - turn the live feeder supplier wave into a controlled commercial launch path for new products
  - finish screening the active live price file in measurable stages
  - review passes and near-misses with clear reasons
  - release only small approved test orders
  - monitor outcome against conservative lower and upper bands

## Non-goals
- Do not do:
  - do not optimize for exact monthly sales prediction
  - do not treat stale approval/recommendation outputs as current launch truth
  - do not auto-buy from the supplier list without explicit user review
  - do not widen scope to multiple supplier waves before this launch path is under control
  - do not patch downstream outputs to make the launch story look cleaner than it is

## Current state
- What already exists:
  - sold-truth and pass-review work now supports conservative commercial judgement
  - the active feeder supplier queue is `stocklist_supplier`
  - the active live supplier file already has substantial screening truth on disk:
    - `42856` row-state rows
    - `266` current pass rows
    - `9721` timeout rows
    - `32869` pending rows
  - current scrape evidence already shows meaningful commercial shape:
    - `266` pass rows
    - `162` rescan rows
    - `3969` fail rows
- What is broken or unsafe:
  - the current recommendation and approval outputs are stale and supplier-misaligned
  - PO handoff is not yet a trustworthy release surface for this supplier wave
  - too many rows are still pending for the launch surface to be treated as complete

## Target state
- one launch baseline exists for the active supplier wave with fresh counts and timestamps
- one pass pack exists for candidates worth commercial review now
- one near-miss pack exists for candidates that just failed and may deserve a second look
- one explicit user-veto step exists before any row reaches test-buy release
- one approved release pack exists for controlled test orders
- one monitored learning pack exists for 14-day, 30-day, and 60-day post-launch review

## Commercial decision model
- This phase uses bands, not point forecasts.
- For each candidate, the system should aim to answer:
  - lower sales band
  - expected sales band
  - upper sales band
  - conservative starter quantity
  - first blocker if it fails
- Pass logic should favour:
  - consistency over one-off spikes
  - conservative lower-band profit
  - avoiding negative-mode products
  - avoiding weak-rank, weak-margin, or structurally poor listings
- Near-miss logic should identify:
  - products that fail on one main blocker only
  - products the user may still want to consider manually

## Systems touched
- Flow(s):
  - F flow primary
  - B/E/F sold-truth evidence used as calibration context only
- Shared dependencies:
  - `out/systems/F/inbox/suppliers/stocklist_supplier/raw_current.csv`
  - `out/systems/F/inbox/suppliers/stocklist_supplier/canonical_current.csv`
  - `out/systems/F/inbox/supplier_price_list_queue_state.csv`
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/systems/F/live/feeder_legacy_first_checks_live.csv`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/analysis_reports/f_live_test_readiness_pack_latest.csv`
  - `out/analysis_reports/f_pass_gate_review_pack_latest.csv`
- Runtime or ownership concerns:
  - no overlapping `F061` runs are allowed
  - controlled refresh windows must snapshot counts before and after runs

## File and output ownership
| Item | Planned owner | Input or output | Path | Notes |
|---|---|---|---|---|
| Active supplier queue state | existing F owner | input | `out/systems/F/inbox/supplier_price_list_queue_state.csv` | proves which supplier wave is live |
| Canonical row-state truth | existing `F061` owner | output | `out/systems/F/live/f_screening_row_state_live.csv` | single screening state source |
| Current pass rows | existing `F061` owner | output | `out/systems/F/live/feeder_legacy_first_checks_live.csv` | current pass list |
| Scrape evidence | existing `F061` owner | output | `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv` | pass, fail, rescan evidence |
| Launch baseline audit | planned `scripts/one_off/F018_build_live_price_file_launch_pack.py` | output | `out/analysis_reports/f_live_price_file_launch_baseline_latest.csv` | fresh supplier-wave counts and launch readiness |
| Pass review pack | planned `scripts/one_off/F018_build_live_price_file_launch_pack.py` | output | `out/analysis_reports/f_live_price_file_pass_review_latest.csv` | pass rows with bands, starter qty, and reasons |
| Near-miss review pack | planned `scripts/one_off/F019_build_live_price_file_near_miss_pack.py` | output | `out/analysis_reports/f_live_price_file_near_miss_review_latest.csv` | just-failed rows with first blocker and recovery hint |
| User release shortlist | planned `scripts/one_off/F019_build_live_price_file_near_miss_pack.py` plus decision log | output | `out/analysis_reports/f_live_price_file_release_shortlist_latest.csv` | final user-reviewed candidates only |
| PO handoff ready set | existing `F050` owner or later controlled builder | output | `out/systems/F/live/feeder_po_handoff_ready_live.csv` | only after explicit approval |
| Post-launch monitoring pack | planned later batch | output | `out/analysis_reports/f_live_price_file_test_monitor_latest.csv` | launch cohort outcome checkpoints |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `supplier_price_list_health.csv` | older than current supplier run | source file missing or wrong supplier | supplier list fetch and conversion health | current source is `stocklist_supplier` |
| `f_screening_row_state_live.csv` | older than latest controlled refresh | no row-state for active supplier | screening truth freshness | current wave is incomplete but usable for baseline |
| `feeder_candidate_recommendations_live.csv` | older than current screening truth | supplier-misaligned with current wave | stale derived recommendation check | currently stale for launch use |
| `feeder_approval_queue_live.csv` | older than current screening truth | supplier-misaligned with current wave | stale approval-surface check | currently stale for launch use |
| `feeder_po_handoff_ready_live.csv` | zero rows after approved release | contract defect on approved rows | PO handoff health | currently expected to stay zero until approval phase |

## Integration points
- APIs:
  - existing F screening and scrape path only
- Sheets:
  - none in this plan
- Local DB:
  - none in this plan
- CSV or file handoffs:
  - supplier raw and canonical files
  - screening truth files
  - analysis review packs
  - later approved PO handoff file

## Risks and mitigations
- Risk:
  - we drift back into exact-forecast thinking
  - Mitigation:
    - lower-band starter logic is the governing rule in this plan
- Risk:
  - stale recommendation or approval files are mistaken for the current launch surface
  - Mitigation:
    - Phase 1 explicitly invalidates stale surfaces and rebuilds from current row-state truth
- Risk:
  - the supplier wave is too large to review without structure
  - Mitigation:
    - split outputs into pass, near-miss, and reject lanes with explicit blocker reasons
- Risk:
  - too many pending rows tempt uncontrolled long-run scanning
  - Mitigation:
    - use controlled refresh windows with milestone counts, not open-ended blind running
- Risk:
  - new-product test buys get released without clear operator control
  - Mitigation:
    - require explicit user-veto review before PO-ready release

## Phase list

### Phase 0 - planning lock and operating rules
- lock the commercial rule:
  - be a bit fussy
  - use lower-band logic
  - keep user veto before any test order
- write the active plan folder and runbook

### Phase 1 - live supplier-wave baseline refresh
- freeze the active supplier wave
- refresh current screening truth for `stocklist_supplier`
- record exact counts for:
  - raw rows
  - canonical rows
  - pending rows
  - timeout rows
  - pass rows
  - rescan rows
- explicitly mark stale derived outputs as not launch-safe

### Phase 2 - launch review surfaces
- build the fresh pass review pack for the current supplier wave
- build the near-miss review pack
- make first blocker, conservative band, and starter qty visible

### Phase 3 - operator commercial review
- review pass rows first
- review near-miss rows second
- let the user say:
  - yes, test this
  - no, reject this
  - watch this
- record explicit decision reasons

### Phase 4 - controlled test-order release
- produce a release shortlist from user-approved rows only
- move approved rows into PO handoff preparation
- keep starter quantities small and conservative

### Phase 5 - monitored post-launch learning
- track approved launch cohort at 14-day, 30-day, and 60-day checkpoints
- compare actual outcomes to lower and upper bands
- classify:
  - healthy conservative pass
  - acceptable but weaker than expected
  - false green
  - operationally bad despite sales
- use repeated outcome patterns to tune pass checks

## Success monitoring
- active supplier wave is explicit and stable
- stale approval surfaces are no longer used as launch truth
- pass review pack exists and is readable
- near-miss review pack exists and is readable
- approved release shortlist count is explicit
- PO-ready rows are explicit after user approval
- post-launch monitoring pack exists for the launch cohort
- launch tuning focuses on reducing weak tests, not on forcing exact prediction

## Proof rules
- What counts as code fix applied:
  - new active plan folder exists with brief, plan, coding plan, runbook, plan status, and batch file
- What counts as isolated verification passed:
  - current live supplier wave evidence is recorded in the plan
  - the plan clearly separates stale launch surfaces from trustworthy screening truth
- What counts as live loop verification confirmed:
  - not applicable in this planning ticket
  - runtime proof will be required in later execution batches

## Batch list
- Batch 001:
  - freeze the active supplier wave and rebuild the launch baseline from current screening truth
- Batch 002:
  - build pass review and near-miss review packs for the active supplier wave
- Batch 003:
  - add operator decision logging and release shortlist
- Batch 004:
  - move approved rows into controlled PO handoff readiness
- Batch 005:
  - build launch-cohort monitoring and learning checkpoint packs

## Archive rule
- When this plan can move to archive:
  - after the first supplier-wave launch path is built, reviewed, used for real test-buy decisions, and either promoted into a stable feeder operating ticket or replaced by a broader multi-supplier launch plan
