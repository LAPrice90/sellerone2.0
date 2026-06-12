# SO21 Foreman Pilot Activation - 2026-06-11

## Purpose

Start a small live Foreman pilot so Luke does not have to manually check whether worker jobs have finished.

## Plain-English Job

The Foreman pilot is the shift manager.

It should:

- check active worker jobs
- check whether expected result reports exist
- spot no-progress work
- spot finished work
- keep urgent work in priority order
- tell the Rep chat what needs a decision
- dispatch the next safe approved worker when no decision is needed

It must not become the old noisy manager loop.

## Current Priority Order

1. A2-T2AC-TW3L active floor risk:
   - `A2-T2AC-TW3L-FLOOR-NOT-UPDATED-ACTIVE-RISK`
   - `H-A2-T2AC-TW3L-TOKEN-SELECTION-ORDERING-REPAIR`
   - Reason: fresh receipt tokens exist, H still selects an older fallback token, no clean floor is produced, and the board/MOT failed to keep this visible as an active pricing risk.
   - This is the top active safe work until the H token-selection repair result exists or a protected Luke decision is needed.
   - Pricing/floor audit found wider exposure: red SKUs are `A2-T2AC-TW3L`, `CN-NR50-TSFE`, `LV-425G-BY4X`, and `6V-EEC1-2S9Z`.
   - Audit result: `CONTROL/BUSINESS_RISK_AUDIT_PRICING_FLOORS_V1_RESULT_20260612.md`.
   - Foreman must not close the pricing/floor risk as solved just because A2 gets a report. It must close the wider red-SKU risk into complete, next packet created, blocked with reason, or Luke decision needed.
   - Protected boundary: no price change, token-ledger edit, Google Sheet write, queue edit, runtime restart, Task Scheduler change, Amazon action, or output deletion.
2. Foreman proof closure rule:
   - `FOREMAN-PROOF-CLOSURE-RULE-20260612`
   - Reason: the manager layer is failing to close finished worker results into complete, next packet, Luke decision, or blocked reason.
   - Keep enforcing this rule on every worker result.
3. New product review AI decision-step rebuild:
   - `NEW-PRODUCT-REVIEW-AI-DECISION-STEP-REBUILD`
   - Dispatch only after proof closure is enforced.
4. Bliss SKU refresh rerun:
   - `BLISS-DISTRIBUTION-SKU-REFRESH-RERUN-WITH-FRESH-SOURCE`
   - Dispatch only after proof closure is enforced.
5. Runtime Watch and MOT:
   - `RUNTIME-WATCH-AND-MOT-VISIBILITY`
   - Dispatch only after proof closure is enforced.
6. H token selection follow-up:
   - `H-TOKEN-SELECTION-FOLLOW-UP-20260612`
   - Dispatch only after proof closure is enforced.
7. Morning MOT Watch:
   - `MORNING-MOT-WATCH-20260612`
   - Dispatch only after proof closure is enforced.

## Allowed Actions

The Foreman pilot may:

- read control files
- read approved task packets
- read worker result reports
- write a short Foreman status report
- recommend the next bounded worker
- flag completed or stuck worker jobs
- start one safe worker thread for an approved, non-protected packet
- record worker thread IDs and expected result files
- update the simple board when a worker starts, finishes, or blocks

## Current Missing Result To Watch

If this file is missing, the next safe Foreman action is the proof-closure rule:

- `CONTROL/FOREMAN_PROOF_CLOSURE_RULE_RESULT_20260612.md`

Approved packet:

- `tasks/approved/MGR_FOREMAN_PROOF_CLOSURE_RULE_20260612.md`

## Temporary Dispatch Hold

Until `CONTROL/FOREMAN_PROOF_CLOSURE_RULE_RESULT_20260612.md` exists, Foreman must not dispatch side work.

Allowed during this hold:

- close already-finished result files into board updates
- update `CONTROL/FOREMAN_LIVE_PILOT_STATUS.md`
- dispatch only the proof-closure rule packet
- escalate if the proof-closure result cannot be produced

Not allowed during this hold:

- dispatch restocking side work
- dispatch profit dashboard work
- dispatch broad MOT repair work
- dispatch new product review implementation
- dispatch Bliss rerun
- dispatch runtime work
- dispatch any protected business action

## Forbidden Actions

The Foreman pilot must not:

- change prices
- edit token ledgers
- write Google Sheets
- edit business queues
- align Product DB or local DB facts
- stop or restart business runtime
- change Windows Task Scheduler
- touch Amazon login or security
- delete outputs
- relaunch the old autonomous worker loop

## Live Pilot Rule

This is a controlled pilot, not a full autonomous relaunch.

Foreman must not end a check in a silent idle state when safe approved work exists.

Foreman must manage by objective, not by report count.

If a result file says the objective is not achieved, Foreman must immediately close it into one of:

- next safe packet created
- Luke decision needed
- blocked with reason
- complete only if the objective is genuinely achieved

Foreman must not treat "a report exists" as success when the report says more work is needed.

Each check must end with one of these outcomes:

- safe worker dispatched
- existing worker still active and worth waiting for
- job blocked with a real reason
- Rep chat escalation needed for a protected decision

Success means:

- Luke can ask the Rep chat for progress
- the Rep chat has a fresh Foreman status to read
- completed worker results are noticed quickly
- urgent jobs do not sit invisible
- safe approved jobs do not wait for Luke to nudge them manually

Failure means:

- too much noise
- repeated no-action reports
- unclear ownership
- any attempt to touch protected business actions

If failure happens, pause the pilot and keep worker launching manual until the Foreman code is repaired.

## Expected Output

The pilot should keep updating:

- `CONTROL/FOREMAN_LIVE_PILOT_STATUS.md`

The report should be short and business-readable.
