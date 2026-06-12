# System Trust Reset And Blindspot Audit - 2026-06-12

Job ref: `SYSTEM-TRUST-RESET-AND-BLINDSPOT-AUDIT`

## Plain-English Verdict

The current management system is not yet trustworthy enough to guide Luke while he is away.

It can create reports, boards, and worker packets, but it has failed at the most important management job:

- spot business risk before Luke spots it
- keep urgent work at the top
- prove that a job actually works
- separate "blocked safely" from "business risk solved"

The A2-T2AC-TW3L pricing issue is the proof. The system saw warning evidence, but the board still parked the issue instead of keeping pressure on it.

## Immediate Direction

Stop treating the board as a trusted control system.

For now, it is only a visible checklist.

The source of truth must become a short daily risk audit that checks business-critical paths directly.

## What Changes Now

### 1. No More Cosmetic Progress

A job is not allowed to look healthy just because:

- a report exists
- a guard blocked a write
- a worker finished
- a board card moved
- a test passed in isolation

The only useful question is:

Did the business risk actually reduce?

### 2. Daily Business Risk Audit Comes First

Before adding more features, the manager must check:

- are prices safe?
- are repricer floors current?
- are token costs being selected correctly?
- are scanners moving?
- are finished F scans reaching review?
- are restocking inputs fresh?
- are MOT warnings turning into active jobs?
- are worker results being closed into real outcomes?

### 3. Urgent Money Paths Must Sit Above System Building

Priority order until stable:

1. Pricing and floor risk
2. Repricing/token selection correctness
3. Business runtime health
4. Finished scan to review handoff
5. Restocking decision readiness
6. Foreman/worker system upgrades
7. Dashboards and nice-to-have views

### 4. Manager Must Report Failures, Not Hide Them

If something is blocked, the board must say:

- what is blocked
- why it matters
- who owns the next move
- what proof clears it

Blocked is not parked.

Blocked means pressure stays on until fixed or explicitly accepted.

## Known Blindspots To Audit

### Pricing/Floor Control

Known failure:

- A2-T2AC-TW3L had fresh receipt tokens, but H still selected old fallback tokens.
- MOT warning existed, but it did not become a loud active business-risk job.

Audit must check:

- all SKUs with fresh stock tokens
- all SKUs with `token_selection_conflict`
- all SKUs with missing floor after a run
- all SKUs with no repricer write after a cost change
- all SKUs where observed/live price is below safe floor or break-even

### Runtime Health

Known concern:

- Luke has repeatedly had to ask if anything is running.

Audit must check:

- cycle alive state
- row progress
- last successful output
- last stuck reason
- whether the stuck detector is too sensitive for 25-row batches

### F Scan To Review

Known concern:

- Passed products may not reliably reach the AI/user review stage.

Audit must check:

- finished price lists
- passed rows
- AI decision state
- final handoff state
- UI visibility

### Restocking

Known concern:

- Restocking may depend on stale proof files or old bridge data.

Audit must check:

- whether O inputs are fresh
- whether old bridge files are blocking real work
- whether the system can produce a usable buying list

### Manager/Foreman

Known failure:

- Foreman can close reports but still miss the real objective.

Audit must check:

- jobs with result files but unresolved business risk
- jobs stuck in wrong board sections
- jobs waiting for proof with no timed follow-up
- safe approved work not being picked up

## Immediate Jobs Created From This Audit

1. `H-A2-T2AC-TW3L-TOKEN-SELECTION-ORDERING-REPAIR`
   - Fix the active pricing risk.

2. `BUSINESS-RISK-AUDIT-PRICING-FLOORS-V1`
   - Find other SKUs with the same type of pricing/floor risk.

3. `MOT-TO-BOARD-ESCALATION-REPAIR-V1`
   - Make MOT warnings become active board work when they affect money or runtime.

4. `WORKER-RESULT-OBJECTIVE-CLOSURE-AUDIT-V1`
   - Check whether finished worker reports actually reduced the business risk they were meant to solve.

## Decision

This is no longer a normal improvement phase.

This is a trust reset.

Until this audit is clean, SellerOne Manager should not be sold to Luke as autonomous. It is a supervised control desk with weak spots being actively repaired.

