# H Seller Detail Retry Recovery Blueprint

## 1. Purpose

This document defines the phased plan to repair H seller-detail retry behavior so suppressed and non-suppressed SKUs do not get stuck in repeated `DETAIL_SKIPPED_ROTATION` and `SELLER_DETAIL_HOLD` states.

This blueprint covers:
- plain-English problem statement
- target behavior
- phased implementation plan
- test plan
- proof plan
- operator-visible expected outcomes

References:
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- `project_control/DECISIONS.md`
- `project_control/CURRENT_STATE.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/api/get_pricing.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/h/h_suppression_truth.py`

## 2. Human Summary

Right now, many SKUs are not getting the extra seller-detail data H needs, so H safely refuses to act and some suppressed SKUs get shown as `SUPP_BLOCKED`. After this work, you should expect to see fewer SKUs stuck in `DETAIL_SKIPPED_ROTATION`, a much smaller `SELLER_DETAIL_HOLD` count, clearer separation between "we did not retry enough" and "Amazon returned no detail data", and dashboard labels that tell the truth instead of making safe no-action cases look like failed write attempts.

## 3. Plain-English Summary Of The Problem

The system already has a partial retry idea:
- if seller-detail is skipped or empty, it sets `retry_next_run_flag = 1`

But that is not enough.

What happens today:
- H rotates through a limited set of ASIN detail calls
- some SKUs are skipped by rotation
- those skipped SKUs get marked for retry later
- but they are not force-prioritized strongly enough to guarantee the missing detail is actually fetched soon
- H pricing then runs anyway
- the SKU lands in `SELLER_DETAIL_HOLD`
- if the SKU is also suppressed, the truth layer can label it `SUPP_BLOCKED`

So the current design is:
- "try again later"

What we need is:
- "keep trying until one of two truths is proven"

Those two truths are:
1. we eventually get the seller-detail data
2. Amazon is not returning the detail data even after repeated deliberate attempts

## 4. Current Evidence Snapshot

Observed in current live artifacts:
- `retry_next_run_flag = 1` on `52` SKUs in `out/listing_offer_snapshot_latest.csv`
- `DETAIL_SKIPPED_ROTATION` on `50` of those SKUs
- `DETAIL_EMPTY_RESPONSE` on `2`
- `SELLER_DETAIL_HOLD` on `52` SKUs in `out/phase1_runtime_floor_snapshot_latest.csv`
- `SUPP_BLOCKED` on `8` SKUs in `out/phase1_runtime_floor_snapshot_latest.csv`

Current meaning:
- a large part of the seller-detail problem is not Amazon hard-failing
- it is that rotation is still winning over retry pressure

## 5. Root-Cause Theory

There are three separate issues.

### 5.1 Retry exists only as a flag, not as an enforced retrieval contract

Current system behavior:
- set `retry_next_run_flag = 1`

Missing behavior:
- no hard guarantee that flagged SKUs move to the front of the next detail-attempt window
- no bounded retry loop with explicit result state

### 5.2 Rotation and retry are not clearly separated

Today, a skipped rotation case and a genuine Amazon empty response both get rolled forward, but they mean different things:
- `DETAIL_SKIPPED_ROTATION` = we did not ask Amazon for detail yet
- `DETAIL_EMPTY_RESPONSE` = we asked Amazon and got no offers detail back

These two states must not be treated as the same operational problem.

### 5.3 Truth labeling overstates blocked writes

In `scripts/h/h_suppression_truth.py`, suppression truth currently counts `READ_ONLY_NO_WRITE` as a write attempt for active suppression cases.

That makes some seller-detail-gated SKUs look like blocked suppression writes when what really happened was:
- no safe action was taken because seller-detail proof was missing

## 6. Target State

The repaired system should prove one of these outcomes for every seller-detail-missing SKU:

1. `DETAIL_RECOVERED`
- a later run fetched the missing seller-detail successfully

2. `DETAIL_AMAZON_EMPTY_CONFIRMED`
- repeated deliberate attempts were made
- Amazon still returned no usable offer detail

3. `DETAIL_API_ERROR_CONFIRMED`
- repeated deliberate attempts failed at API level

4. `DETAIL_RETRY_PENDING`
- SKU is still inside bounded retry window and has not exhausted attempts

5. `DETAIL_RETRY_EXHAUSTED`
- the local retry budget was spent without success, so operator attention is needed

Required rule:
- `DETAIL_SKIPPED_ROTATION` must be temporary and should not persist across many runs for the same SKU without explicit operator visibility

## 7. Contract Design

## 7.1 New retry queue contract

Enhance `out/systems/H/live/h_item_offers_retry_queue.csv` to include:
- `sku`
- `asin`
- `marketplace`
- `first_missing_utc`
- `last_attempt_utc`
- `last_success_utc`
- `attempt_count`
- `rotation_skip_count`
- `empty_response_count`
- `api_error_count`
- `detail_status_current`
- `detail_resolution_status`
- `priority_band`
- `force_attempt_next_run_flag`
- `exhausted_flag`
- `operator_reason`

## 7.2 New resolution statuses

Recommended `detail_resolution_status` values:
- `PENDING_RETRY`
- `RECOVERED`
- `AMAZON_EMPTY_CONFIRMED`
- `API_ERROR_CONFIRMED`
- `RETRY_EXHAUSTED`

## 7.3 Dashboard truth labels

Add a separate truth lane for seller-detail gating:
- `DETAIL_GATED`
- `SUPP_GATED_DETAIL`

Do not collapse these into `SUPP_BLOCKED` when no real write attempt happened.

## 8. Required Behavioral Rules

### 8.1 Retry priority rule

Any SKU with `retry_next_run_flag = 1` must be prioritized ahead of new rotation candidates until:
- detail is recovered
- or retry budget is exhausted

### 8.2 Rotation rule

Rotation is allowed only after pending retry-priority SKUs are served up to the allowed per-run detail-attempt budget.

### 8.3 Confirmation rule

Amazon-missing-data must not be declared from a single skip.

It can only be declared after repeated actual attempted calls with:
- `attempted_flag = 1`
- `selected_flag = 1`
- status repeatedly `DETAIL_EMPTY_RESPONSE`

### 8.4 Write-truth rule

Seller-detail-gated `READ_ONLY_NO_WRITE` cases must not be counted as attempted writes in suppression truth.

## 9. Phased Implementation Plan

## Phase 0 - Observability And Contract Lock

Goal:
- make the retry problem measurable before deeper logic changes

Files:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/h/h_suppression_truth.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`

Changes:
- add richer retry queue fields
- surface retry queue counts in logs and dashboard
- separate seller-detail-gated truth from actual blocked writes

Required output:
- operators can see whether the SKU was skipped, attempted, recovered, or exhausted

## Phase 1 - Retry Queue Enforcement

Goal:
- make retry queue priority real instead of advisory

Files:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/api/get_pricing.py`

Changes:
- consume retry queue first before general rotation candidates
- reserve a per-run detail-attempt budget for retry-priority SKUs
- explicitly mark which ASINs were selected because of retry pressure

Required output:
- repeated `DETAIL_SKIPPED_ROTATION` on the same SKU should drop sharply

## Phase 2 - Amazon-Missing Confirmation Logic

Goal:
- separate local scheduling misses from genuine upstream missing data

Files:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/api/get_pricing.py`

Changes:
- add bounded retry thresholds such as:
  - `rotation_skip_threshold`
  - `empty_response_confirm_threshold`
  - `api_error_confirm_threshold`
- promote repeated actual empty responses to `AMAZON_EMPTY_CONFIRMED`
- promote repeated actual API errors to `API_ERROR_CONFIRMED`
- promote repeated unserved retry cases to `RETRY_EXHAUSTED` if local budget/path is the bottleneck

Required output:
- system can answer "is Amazon missing the data or did we fail to fetch it?"

## Phase 3 - H Pricing Gate Alignment

Goal:
- H should price truthfully based on seller-detail resolution status

Files:
- `scripts/phase1/phase1_main_loop.py`
- `scripts/flows/H/H110_run_phase1_h_pilot.py`

Changes:
- keep seller-detail gate for unsafe cases
- pass through richer seller-detail resolution status into H outputs
- distinguish:
  - `SELLER_DETAIL_HOLD_PENDING_RETRY`
  - `SELLER_DETAIL_HOLD_AMAZON_EMPTY_CONFIRMED`
  - `SELLER_DETAIL_HOLD_API_ERROR_CONFIRMED`

Required output:
- blocked SKUs show why they are blocked in a way an operator can understand

## Phase 4 - Health And Alerting

Goal:
- make this issue visible before it becomes a wide portfolio problem

Files:
- `scripts/flows/A/A015_build_system_health_check.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`

Changes:
- add H-scoped health checks for:
  - repeated `DETAIL_SKIPPED_ROTATION`
  - retry queue backlog growth
  - exhausted retry cases
  - confirmed Amazon-empty cases above threshold

Required output:
- H health tells the truth about whether the issue is local scheduling or upstream data absence

## 10. Test Plan

## 10.1 Unit tests for detail status semantics

Files:
- `tests/test_get_pricing_detail_meta.py`

Cases:
- prioritized ASIN is selected and non-selected ASIN is marked `DETAIL_SKIPPED_ROTATION`
- summary-only response is `DETAIL_EMPTY_RESPONSE`
- API error response sets attempted flag and error status

## 10.2 Retry queue enforcement tests

New tests:
- `tests/test_h_item_offers_retry_queue.py`

Cases:
- SKU with `retry_next_run_flag = 1` is selected ahead of fresh rotation candidates
- retry queue reserve budget is honored
- recovered SKU leaves pending retry state
- exhausted SKU is marked correctly after threshold

## 10.3 The key proof test you asked for

New test:
- `test_repeat_attempt_distinguishes_local_skip_vs_amazon_missing_detail`

This test must simulate two separate paths:

Path A - local retry failure
- run 1: SKU skipped by rotation
- run 2: SKU skipped by rotation again
- run 3: SKU forced into retry budget and detail is finally fetched

Expected result:
- system proves the earlier missing data was our scheduling problem, not Amazon
- final status becomes `RECOVERED`

Path B - Amazon-level missing detail
- run 1: SKU selected, attempted, returns `DETAIL_EMPTY_RESPONSE`
- run 2: SKU selected again, attempted, returns `DETAIL_EMPTY_RESPONSE`
- run 3: SKU selected again, attempted, returns `DETAIL_EMPTY_RESPONSE`

Expected result:
- system proves we did actually retry
- final status becomes `AMAZON_EMPTY_CONFIRMED`

This is the most important test in the whole plan because it proves whether the missing data is:
- our retry design failure
- or Amazon not returning the detail

## 10.4 Suppression truth tests

Files:
- `tests/test_h_suppression_truth.py`

Cases:
- suppression-active + `READ_ONLY_NO_WRITE` + seller-detail hold should map to `SUPP_GATED_DETAIL` or equivalent non-attempt status
- `SUPP_BLOCKED` should only appear when a genuine write attempt was made and not applied

## 10.5 H main loop tests

Files:
- `tests/test_phase1_main_loop.py`

Cases:
- seller-detail pending retry holds safely
- seller-detail confirmed Amazon-empty holds safely with explicit reason
- seller-detail recovered resumes normal pricing path

## 10.6 Health tests

Files:
- `tests/test_h_split_health_gate.py` or a new focused H health test file

Cases:
- backlog WARN when retry queue grows beyond threshold
- FAIL or WARN when `DETAIL_SKIPPED_ROTATION` persists beyond allowed consecutive runs
- separate alert for confirmed Amazon-empty cases

## 11. Proof Plan

## 11.1 Isolated proof

Required before runtime claims:
- all new retry queue tests pass
- all status-semantic tests pass
- the repeat-attempt versus Amazon-empty test passes

Minimum proof output:
- count of pending retries
- count of recovered retries
- count of confirmed Amazon-empty cases
- count of true blocked writes

## 11.2 Runtime proof

Required runtime sequence:
1. next H run writes richer retry queue state
2. retry-priority SKUs are actually selected ahead of normal rotation
3. some current `DETAIL_SKIPPED_ROTATION` SKUs become `DETAIL_OK`
4. remaining stubborn cases become `AMAZON_EMPTY_CONFIRMED` or `API_ERROR_CONFIRMED`
5. `SELLER_DETAIL_HOLD` count falls materially
6. `SUPP_BLOCKED` stops overstating seller-detail-gated cases

## 11.3 Runtime success metrics

Initial success window:
- `DETAIL_SKIPPED_ROTATION` backlog materially lower than current baseline of `50`
- `SELLER_DETAIL_HOLD` materially lower than current baseline of `52`
- `SUPP_BLOCKED` no longer used for seller-detail-gated read-only cases
- confirmed Amazon-empty cases are explicitly counted

## 12. Definition Of Done

This issue is only done when all are true:
- retry queue has explicit state and enforced priority
- repeated skipped SKUs are genuinely retried
- system can distinguish local retry failure from Amazon missing detail
- seller-detail-gated read-only cases are no longer mislabeled as blocked writes
- targeted tests pass
- runtime evidence shows lower `DETAIL_SKIPPED_ROTATION` and `SELLER_DETAIL_HOLD`

## 13. Recommended Delivery Order

1. Observability contract and truth-label cleanup
2. Retry queue enforcement
3. Amazon-empty confirmation logic
4. H pricing gate alignment
5. Health and dashboard rollout
6. Runtime proof review

## 14. What You Should Expect To See

When this is working properly, you should see the system stop silently carrying the same SKUs forward forever. Some missing-data SKUs will start recovering on later H runs because retry priority will force them through. A smaller set will be shown clearly as "Amazon did not return detail after repeated attempts". The big pile of `DETAIL_SKIPPED_ROTATION` should shrink, `SELLER_DETAIL_HOLD` should shrink, and `SUPP_BLOCKED` should only remain on genuine blocked-write cases rather than safe read-only holds.
