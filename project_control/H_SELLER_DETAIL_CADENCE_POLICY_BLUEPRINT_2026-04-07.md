# H Seller Detail Cadence Policy Blueprint

## 1. Purpose

This blueprint defines the next stage after Phase 5C.

The system now tells the truth about seller-detail gaps. The next stage is to reduce locally caused blank-detail outcomes by changing retry selection policy, while keeping Amazon-upstream missing cases explicitly separate.

This is a planning artifact only. No code change is part of this document.

References:
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `project_control/H_SELLER_DETAIL_HOME_TIME_MEASUREMENT_PLAN_2026-04-07.md`
- `project_control/H_SELLER_DETAIL_RETRY_RECOVERY_BLUEPRINT_2026-04-07.md`
- `scripts/cycles/run_H_pricing_cycle.py`
- `out/systems/H/live/h_seller_detail_measurement_summary_latest.csv`
- `out/systems/H/live/h_seller_detail_measurement_alerts_latest.csv`
- `out/systems/H/live/h_seller_detail_operator_review_latest.csv`

## 2. Human Summary

Plain English: the repricer is no longer mainly the problem. We now need to stop local retry cadence from creating blanks. The next stage gives cadence-heavy SKUs a protected retry path, keeps likely Amazon-missing SKUs out of that path, and proves whether this reduces blanks for the right reason.

## 3. Current Baseline (Live Evidence)

Latest summary row:
- `snapshot_utc=2026-04-07T12:16:33Z`
- `run_id=20260407T121633Z`
- `pending_retry_count=0`
- `recovered_count=15`
- `amazon_missing_likely_count=0`
- `retry_exhausted_count=50`
- `supp_gated_detail_count=6`
- `supp_blocked_count=1`

Latest alert row status:
- `pending_retry_growth=ok (delta=-1)`
- `retry_exhausted_growth=ok (delta=1, threshold=3)`
- `amazon_missing_pressure=ok`
- `stale_pending_pressure=ok`

Current shape:
- most stuck rows are in `RETRY_EXHAUSTED`
- most review rows are bucketed `LIKELY_LOCAL_SELECTION_CADENCE`
- seller-detail story is now visible, but action policy is not yet optimized

## 4. Problem Statement

The system currently classifies well but does not yet apply a dedicated policy that treats:
- local cadence pressure
- Amazon upstream missing
- genuine blocker cases

as separate operational tracks.

Without policy separation, `RETRY_EXHAUSTED` can become a holding bucket instead of a decision bucket.

## 5. Phase Goal

Move from truthful diagnosis to controlled behavior change:
- reduce local-cadence-induced blanks
- protect core flow safety and publish integrity
- avoid wasting attempt budget on likely upstream-missing cases
- preserve clear operator visibility

## 6. Scope And Non-Goals

In scope:
- H retry selection policy for seller-detail attempts
- protected retry lane design
- fairness and lane-cap rules
- operator decision contract for exhausted cases
- H-scoped tests and proof requirements

Not in scope:
- changing pricing formulas or floor/ceiling logic
- changing A cycle logic
- changing Google Sheets directly
- masking outputs downstream to appear improved

## 7. Policy Model

Bucket policy contract:
- `LIKELY_LOCAL_SELECTION_CADENCE`: eligible for protected retry lane
- `LIKELY_AMAZON_UPSTREAM`: limited attempts, then remain upstream bucket unless new evidence appears
- `RETRY_EXHAUSTED_OPERATOR_REVIEW`: manual review bucket with defined operator actions
- `GENUINE_PRICING_OR_SUPPRESSION_BLOCKER`: handled outside seller-detail retry logic

Core rule:
- no SKU should be classified as Amazon-upstream from skipped rotation alone

## 8. Phased Plan

### Phase 6A - Bucket-to-policy contract

Purpose:
- define exact allowed action by bucket

Expected outputs:
- explicit bucket policy table in code contract docs
- no ambiguous "try again later" states

### Phase 6B - Protected retry lane

Purpose:
- reserve retry capacity for local-cadence bucket SKUs

Policy expectations:
- lane capacity is capped
- lane does not starve normal rotation
- lane exit conditions are explicit

Exit conditions:
- `RECOVERED`
- escalated to `LIKELY_AMAZON_UPSTREAM`
- escalated to `RETRY_EXHAUSTED_OPERATOR_REVIEW`

### Phase 6C - Fairness and prioritization

Purpose:
- avoid SKU starvation and reduce repeated ineffective attempts

Priority factors:
- operator priority
- aging
- suppression impact
- attempt history quality

### Phase 6D - Operator action contract

Purpose:
- convert review output into consistent action

Required operator action lanes:
- continue controlled retries
- accept likely Amazon-upstream status
- manual case review for genuine blockers

### Phase 6E - Live proof and acceptance

Purpose:
- prove policy effect in runtime without breaking H integrity

Proof must show:
- protected lane usage
- unchanged publish/finalize integrity
- post-proof ownership continuation

## 9. Threshold Defaults (Planning)

Proposed defaults:
- `protected_retry_lane_budget = 5`
- `protected_retry_lane_max_share = 0.50`
- `protected_lane_fairness_window_runs = 3`
- `retry_exhausted_threshold = 8`
- `amazon_missing_confirm_threshold = 3`

Rule:
- all thresholds must be named config values, not literals

## 10. Test Plan For Implementation Ticket

Unit tests:
- protected lane selects cadence bucket before normal rotation
- protected lane cap is enforced
- fairness prevents same small subset from monopolizing lane
- Amazon-upstream bucket does not consume protected lane indefinitely
- exit conditions map correctly to next bucket

Contract tests:
- measurement summary reconciles with review rows after policy change
- bucket counts stay internally consistent
- rerunning same run ID remains idempotent

Runtime proof tests:
- post-change run emits policy usage marker
- post-change run finalizes and publishes
- next run starts after proof run

## 11. Runtime Proof Contract

For implementation phase, proof language must remain:
- `code fix applied`
- `isolated verification passed`
- `live loop verification confirmed`

Minimum runtime evidence:
- `publish_commit_end run_id=<RUN_ID>`
- `h_batch_state_transition run_id=<RUN_ID> from=published to=finalized`
- `run_completed_marker written run_id=<RUN_ID>`
- `publish_proof_check current=<RUN_ID>`
- next run observed in `H_runtime_status.json`

## 12. Risk Controls

Main risks:
- protected lane starvation of normal flow
- over-labeling Amazon-upstream too early
- operator overload if exhausted bucket grows without action policy

Controls:
- lane cap and share cap
- fairness window
- strict classification requirement for Amazon-upstream
- keep alert output active and visible

## 13. Expected Outcomes

Best case:
- fewer locally caused blanks
- more cadence-bucket SKUs move to `RECOVERED`
- faster separation of true upstream-missing cases

Expected case:
- some SKUs remain exhausted, but with cleaner reasons and faster handling

Failure signal:
- exhausted growth with no recovery lift and no evidence of protected lane impact

## 14. Definition Of Done For Phase 6

Phase 6 is done when all are true:
- bucket policy is explicit and implemented
- protected lane behavior is proven on live run
- H publish/finalize safety is unchanged
- post-proof next run is observed
- operator can answer "local cadence vs Amazon upstream vs genuine blocker" in one pass

## 15. Execution Gate

This blueprint is ready for implementation ticketing.

Recommended execution ticket:
- `H seller-detail cadence policy and protected retry lane implementation (Phase 6A-6E)`

## 16. No-Coding Declaration

This document is planning-only and introduces no runtime code change.
