# SO21 Runtime Maintenance Scheduler State Blocker

Created UTC: 2026-06-08T19:18:00Z
Role: Operations

## Blocker

`SO21-RUNTIME-MAINTENANCE-CONTROL` cannot be treated as proved yet.

The Reviewer found that `CONTROL/RUNTIME_CONTROL.md` was built from older scheduler evidence that said the visible Windows scheduled tasks were disabled. A read-only `Get-ScheduledTask` check by the Reviewer found current machine state does not match that older evidence.

## Affected Job

- `SO21-RUNTIME-MAINTENANCE-CONTROL`
- related review: `SO21-RUNTIME-MAINTENANCE-CONTROL-REVIEW`

## What Was Attempted

The Reviewer inspected:

- `CONTROL/RUNTIME_CONTROL.md`
- `CONTROL/SO21_RUNTIME_MAINTENANCE_CONTROL_REVIEW_HANDOFF.md`
- `tasks/approved/MGR_SO21_RUNTIME_MAINTENANCE_CONTROL_REVIEW.md`
- `CONTROL/DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md`
- `CONTROL/DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.csv`
- `CONTROL/WINDOWS_SCHEDULER_PAUSE_DECISION.md`
- `CONTROL/WINDOWS_SCHEDULER_PAUSE_PROOF.csv`
- read-only current scheduler state

## What Failed

The older control evidence said all 11 visible Windows scheduled tasks were disabled. The Reviewer observed current machine state as:

- `Ready`: `AMZ Controlled Restart`, `AMZ H Cycle`, `AMZ Morning MOT Post A`, `AMZ Morning MOT Post Restart`, `AMZ Orders`, `AMZ Price List Manager`, `AMZ Pricing Summary`, `SellerOne Manager Hourly MOT`
- `Running`: `AMZ Pricing Summary Hourly`
- `Disabled`: `AMZ Restart Postcheck`, `Codex_H_Phase1_OneShot`

This does not prove the runtime-control document is unsafe in design, but it does mean the scheduler-state evidence is stale and the maintenance map must be reconciled before it is used as a planning base.

## Safest Proposed Fix

Open a read-only scheduler-state reconciliation packet:

- record current Windows scheduled task state
- compare it to `WINDOWS_SCHEDULER_PAUSE_DECISION.md`, `WINDOWS_SCHEDULER_PAUSE_PROOF.csv`, and `RUNTIME_CONTROL.md`
- update control evidence only
- mark any actual pause, disable, enable, restart, delete, or scheduler edit as requiring explicit Luke approval

## Protected Boundary

No scheduler change, runtime change, service restart, worker restart, automation change, queue movement, database write, Sheet write, price change, output deletion, Amazon/security action, permanent deletion, compression, purge, archive apply, or file rename was performed by Operations while recording this blocker.

## Current Status

Operations moved `SO21-RUNTIME-MAINTENANCE-CONTROL` to `retest_failed` because Reviewer proof returned a concrete gap.
