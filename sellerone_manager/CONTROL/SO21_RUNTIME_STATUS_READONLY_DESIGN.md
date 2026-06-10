# SO21 Runtime Status Read-Only Design

Job: `SO21-RUNTIME-STATUS-READONLY-DESIGN`
Created: 2026-06-08
Mode: design only

## Plain-English Purpose

Before SellerOne can safely pause or restart anything, Operations needs a trusted read-only status view.

This is the inspection step. It shows what appears to be running, ready, disabled, stale, protected, or unknown. It must not change anything.

## What It Should Answer

- Which visible SellerOne Windows scheduled tasks exist?
- What state are they in now?
- Which tasks are Business Runtime, Control Desk Automation, or Maintenance Protected?
- Which control automations are active?
- Which evidence is fresh and which is stale?
- Are any maintenance records active?
- Are there locks or worker ownership markers that make maintenance risky?
- What decisions are protected and need Luke?

## Evidence Inputs

Future implementation may read:

- `CONTROL/RUNTIME_CONTROL.md`
- `CONTROL/SO21_SCHEDULER_STATE_RECONCILIATION.md`
- `CONTROL/CURRENT_STATE.md`
- `CONTROL/CURRENT_TICKETS.md`
- `CONTROL/OPERATIONS.md`
- Codex automation definitions
- read-only Windows scheduled-task metadata
- `out/locks`
- MOT evidence under `out/systems/M/mot`
- future maintenance records under the maintenance record folder

## Output Shape

The status view should write a clear report under `CONTROL/`.

Suggested sections:

- current summary
- scheduler status
- Codex automation status
- active maintenance records
- locks and ownership warnings
- stale evidence warnings
- protected decisions needed
- recommended next safe action

## Refusal Rules

The read-only status tool must refuse to:

- pause runtime
- restart runtime
- kill a process
- enable or disable a scheduled task
- edit Task Scheduler
- mutate Codex automations
- change prices
- write Google Sheets
- align databases
- delete or move outputs
- touch Amazon login/security

## Stale Evidence Rule

If fresh machine state disagrees with older control evidence, the tool must say so plainly.

It must not hide the mismatch and must not choose one silently.

## Success Criteria

This design is ready for review when:

- it is clear what evidence the future tool reads
- it is clear what report the future tool writes
- it is clear that no state changes are allowed
- stale scheduler evidence is handled explicitly
- protected boundaries are visible

## Current Next Move

Review this design, then decide whether a Worker should build the read-only status tool.
