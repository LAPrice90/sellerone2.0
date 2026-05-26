# H Seller Detail Home Time Measurement Plan

## 1. Purpose

This document defines the next step after the seller-detail retry logic fix and visibility fix.

The logic is now behaving truthfully. The next job is to measure the remaining missing-detail problem in home time mode so SellerOne can prove:

- which SKUs recover when retried
- which SKUs remain missing because Amazon is not returning the detail
- how fast the backlog is clearing
- whether remaining `SUPP_BLOCKED` cases are genuine blockers or just older state

This plan is for execution in the live H runtime using the existing guarded launcher and restart-drain protocol.

References:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `project_control/H_SELLER_DETAIL_RETRY_RECOVERY_BLUEPRINT_2026-04-07.md`
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/h/h_suppression_truth.py`
- `out/systems/H/live/h_seller_detail_resolution_proof_latest.csv`

## 2. Human Summary

Plain English: the repricer logic is no longer the main problem. The next move is to let H keep running in home time mode while Codex adds a measurement layer that shows, over repeated runs, whether missing seller detail is being recovered or whether Amazon is simply not sending it. After this phase, you should expect to see a simple aging view of stuck SKUs, a clean split between recoverable cases and likely Amazon-missing cases, and a much more reliable answer when you ask "is this our bug or Amazon data?"

## 3. Current Standing

Latest proven runtime evidence:
- seller-detail retry logic is live
- seller-detail visibility fields are live
- runtime proof artifact is live

Most recent proven evidence run:
- `run_id=20260407T105459Z`

Proven counts from live proof artifact:
- `pending_retry_count=50`
- `recovered_count=15`
- `supp_gated_detail_count=5`
- `supp_blocked_count=2`

Current strategic meaning:
- local retry logic now works
- remaining missing-detail pressure is now measurable
- next uncertainty is upstream data availability, not repricer logic correctness

## 4. Planning Position Against Roadmap

Roadmap context:
- H remains `Needs Stabilising`
- next focus remains runtime stability plus truthful evidence

Expectation fit:
- this phase is allowed under H planning tolerance because it is H-scoped observability and measurement work
- current live runtime is operational
- there is no active proven H hard-block in newer live evidence
- older aggregate checklist files may be stale and must not override newer runtime truth

## 5. Phase Goal

Goal of this next phase:

Build and prove a home-time measurement layer that answers, for each seller-detail-missing SKU:

1. Is it still pending retry?
2. Did it recover?
3. Has it been retried enough that Amazon-level missing data is the likely truth?
4. Is it affecting suppression truth or pricing truth right now?

This phase is measurement-first. It should not change pricing decisions unless a root-cause correction is strictly required by the measurement pipeline itself.

## 6. Scope And Non-Goals

In scope:
- rolling seller-detail recovery history
- per-SKU aging
- per-SKU classification
- operator-visible summary outputs
- H-scoped alert conditions for backlog and exhaustion
- home-time proof collection

Not in scope:
- changing Google Sheets directly unless explicitly requested
- changing A cycle behavior
- masking results downstream to look better
- new pricing strategy logic
- portfolio-level optimisation work

## 7. Target Outputs

Codex should deliver these outputs in this phase:

### 7.1 Rolling recovery ledger

New output:
- `out/systems/H/live/h_seller_detail_recovery_history_latest.csv`

Required columns:
- `snapshot_utc`
- `run_id`
- `marketplace`
- `sku`
- `asin`
- `seller_detail_status`
- `seller_detail_resolution_status`
- `retry_next_run_flag`
- `retry_attempt_count`
- `rotation_skip_count`
- `empty_response_count`
- `api_error_count`
- `truth_status`
- `aging_runs`
- `aging_first_seen_utc`
- `aging_last_seen_utc`
- `classification`

### 7.2 Operator summary

New output:
- `out/systems/H/live/h_seller_detail_measurement_summary_latest.csv`

Required summary counts:
- `pending_retry_count`
- `recovered_count`
- `amazon_missing_likely_count`
- `retry_exhausted_count`
- `supp_gated_detail_count`
- `supp_blocked_count`
- `newly_recovered_count`
- `stale_pending_over_threshold_count`

### 7.3 Optional dated archive

If the existing output pattern supports it safely:
- `out/systems/H/live/history/h_seller_detail_measurement_summary_<date>.csv`

## 8. Classification Contract

Codex should implement plain classifications that an operator can trust:

- `PENDING_RETRY`
  - still inside retry window
  - no exhaustion threshold reached

- `RECOVERED`
  - seller detail now available
  - was previously missing

- `LIKELY_AMAZON_MISSING`
  - repeated actual attempted calls
  - repeated empty-detail responses
  - not just skipped by local rotation

- `LIKELY_LOCAL_SELECTION_DELAY`
  - repeated pending retries
  - too many rotation skips relative to attempted detail calls

- `RETRY_EXHAUSTED`
  - local threshold exceeded
  - operator attention required

- `NOT_APPLICABLE`
  - SKU no longer in active missing-detail set

Classification rule:
- Codex must not classify a SKU as `LIKELY_AMAZON_MISSING` from skipped rotation alone.

## 9. Home Time Mode Execution Expectations

Codex must follow these expectations during implementation and proof:

### 9.1 Runtime safety

- use H guarded runtime only
- use restart drain if code reload is required
- never hard-kill the live H owner unless explicitly instructed
- prove ownership restoration after any drain/reload

### 9.2 Proof sequence

For any code change in this phase, Codex must prove all of:

1. code fix applied
2. isolated verification passed
3. live loop verification confirmed

Live loop verification confirmed means:
- a post-change H run reaches publish commit
- the same run reaches finalized state
- the new measurement artifact is written from that same run
- the next H run starts afterward, showing ownership restored

### 9.3 No stale-proof shortcuts

Codex must not use an older checklist snapshot as confirmation if newer runtime evidence exists.

If proof is incomplete, Codex must say:
- `not yet proven`

### 9.4 No ad-hoc A verification

Codex must not run A scripts for this phase unless explicitly asked.

## 10. Phased Delivery

### Phase 5A - Recovery history layer

Purpose:
- create a reliable rolling per-SKU history table

Implementation expectation:
- consume live seller-detail snapshot outputs plus truth outputs
- append or rebuild a stable latest history table
- preserve one row per SKU per run or per snapshot event

Expected visible result:
- operator can see how long a SKU has been stuck and whether it ever recovered

### Phase 5B - Classification and aging

Purpose:
- convert raw retry history into operator-usable truth

Implementation expectation:
- compute `aging_runs`
- compute first-seen and last-seen timestamps
- compute classification using explicit thresholds

Expected visible result:
- stuck SKUs separate into recoverable vs likely Amazon-missing vs exhausted

### Phase 5C - Summary and alert layer

Purpose:
- make the measurement easy to consume

Implementation expectation:
- write summary CSV
- add H-scoped alert conditions for backlog growth and exhaustion growth
- keep flow-owned testing boundaries intact

Expected visible result:
- one quick summary answer for "are we improving or not?"

### Phase 5D - Home time proof run

Purpose:
- prove the new layer in live runtime

Implementation expectation:
- deploy through safe reload if needed
- capture at least one finalized+published post-change run
- confirm new artifact write from that run
- confirm next run starts after proof run

Expected visible result:
- no ambiguity about whether the new layer is live

## 11. Threshold Expectations

These are planning defaults. Codex may refine them if repo patterns suggest better existing thresholds.

Suggested default thresholds:
- `stale_pending_run_threshold = 3`
- `likely_amazon_missing_empty_response_threshold = 3`
- `retry_exhausted_threshold = 8`
- `local_selection_delay_rotation_skip_threshold = 3`

Threshold rule:
- any threshold Codex uses must be named in code or config, not buried as an unexplained literal

## 12. Required Tests

### 12.1 Unit tests

New or extended tests should cover:

- history builder keeps correct latest and prior rows
- aging increments correctly across repeated runs
- `RECOVERED` classification is assigned after prior pending state
- `LIKELY_AMAZON_MISSING` requires actual attempted empty responses
- `LIKELY_LOCAL_SELECTION_DELAY` requires repeated skip pressure
- summary counts reconcile to history rows

### 12.2 Contract tests

Required contract checks:
- schema check for the recovery history output
- schema check for the summary output
- idempotent rerun behavior

### 12.3 Runtime proof check

Required runtime proof after deployment:
- new history output written
- new summary output written
- values align with existing proof artifact counts
- finalized/published run ID linked to new artifact timestamps

## 13. Proof Requirements

Codex must show these proof points before calling the phase done:

- test command and pass count
- post-change H run ID
- proof that new artifact files were written after the code change
- proof that the run finalized and published
- proof that H continued into another run afterward

Minimum proof examples:
- `publish_commit_end run_id=<RUN_ID>`
- `run_completed_marker written run_id=<RUN_ID>`
- `H_last_finalized_run_id.txt == <RUN_ID>`
- `H_cycle_last_publish_run_id.txt == <RUN_ID>`
- recovery history file timestamp newer than code change
- summary file timestamp newer than code change

## 14. Expected Operator Outcome

After this phase, when the user asks "why are these SKUs still blocked?", Codex should be able to answer in one sentence per bucket:

- still pending and likely to recover
- repeatedly tried and Amazon still not returning detail
- exhausted and needs operator review
- genuine suppression/pricing blocker unrelated to seller-detail missing

That is the real business outcome of this phase.

## 15. Definition Of Done For This Phase

This phase is done when all of these are true:

- recovery history artifact exists and is populated
- summary artifact exists and is populated
- classifications are backed by explicit thresholds
- focused tests pass
- one post-change H run finalized and published with the new artifacts
- ownership restored and next H run observed
- remaining uncertainty is reduced from "what is happening?" to "how much is Amazon-caused?"

## 16. What Codex Should Say At The End

Codex should close this phase in plain English like this:

- logic remains fixed
- measurement layer is live
- we now know how many SKUs are recoverable vs likely Amazon-missing
- next step is policy/action on the exhausted or Amazon-missing bucket
