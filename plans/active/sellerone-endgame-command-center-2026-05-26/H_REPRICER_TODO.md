# H Repricer Todo

Created: 2026-05-26
Owner flow: H
Business purpose: maintain pricing and market truth without blocking restock decisions.

## Source Plans To Read First

- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- `project_control/TASK_QUEUE.md`
- active H plans under `plans/active/`

## Current Evidence

- `out/cycle_alerts/summary.csv` shows H has 9 FAIL and 15 WARN.
- H freshness files are stale in current health evidence.
- H market context has a fill failure: zero values in buy box channel, lowest FBA/FBM price, and offer count columns.
- O price-proof completion is blocked because a read-only listing-offer scan should not overlap H ownership.

## Plain-English Finish Line

H is endgame-ready when:

1. It produces fresh pricing and market evidence.
2. It finalizes runs cleanly.
3. It restores scheduler ownership after controlled proof.
4. It does not block O restock market scans without a clear isolation path.
5. Remaining warnings are named and non-blocking.

## Phase 0 - Classify H Failures

- [ ] Separate current H failures into `blocks restock`, `blocks repricing`, `stale evidence`, and `monitor only`.
- [ ] Confirm whether H owner is currently running, paused, or stalled.
- [ ] Do not treat stale health as current truth when newer runtime evidence exists.
- [ ] If H proof is required, use controlled H proof rules, not ad-hoc health-only proof.

Success condition:
- Each H FAIL has one owner category and next action.

## Phase 1 - Restore Fresh Terminal And Publish Evidence

- [ ] Confirm latest terminal marker and publish marker age.
- [ ] Confirm whether scheduler ownership is active.
- [ ] If ownership is broken, plan controlled restart or H proof before touching O market files.

Success condition:
- H can show a fresh finalized run or a clear parked reason.

## Phase 2 - Support O Market-Proof Window

- [ ] Decide whether H can be paused safely for the O 59-row read-only scan.
- [ ] If yes, use the documented pause, scan, rebuild, resume, and proof path.
- [ ] If no, record exact blocker and park O price-proof completion.

Success condition:
- O gets a safe market-proof window or a truthful blocked status.

## Phase 3 - Reduce Non-Blocking H Noise

- [ ] Review H warnings after active FAILs are handled.
- [ ] Put accepted warnings on a named exception list with reason and review cadence.
- [ ] Keep warnings visible in health; do not hide them.

Success condition:
- H is stable enough to stop interrupting unrelated work outside morning MOT.

## Stop Conditions

Stop before changing anything if:

- H isolation requires elevated admin action
- scheduler ownership cannot be proven after a test
- a task asks for mid-cycle health judgment
- O or F wants to use H-owned market files while H is actively writing them

