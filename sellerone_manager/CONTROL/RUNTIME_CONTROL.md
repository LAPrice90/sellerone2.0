# SellerOne Runtime Control

Job: `SO21-RUNTIME-MAINTENANCE-CONTROL`
Created: 2026-06-08
Mode: planning only

## Plain-English Status

This document is the maintenance-mode blueprint for SellerOne runtime control.

It does not pause, restart, disable, enable, edit, delete, or create any runtime, scheduler, service, worker, automation, queue, price, Sheet, database, output, Amazon, or script implementation state.

Think of this file like a labeled breaker panel. It tells a future worker which switches look like business runtime, which switches look like control-desk reporting, and which switches must stay protected until Luke approves a specific maintenance action.

## Evidence Used

This map is based only on existing control evidence:

- `sellerone_manager/CONTROL/DEAD_AUTOMATION_AND_SCHEDULER_REVIEW.md`
- `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md`
- `sellerone_manager/CONTROL/RUNTIME_SAFETY_RULES.md`
- `sellerone_manager/tasks/approved/MGR_SO21_RUNTIME_MAINTENANCE_CONTROL.md`

No live Task Scheduler query or Task Scheduler modification was performed for this document.

## Scheduler-State Addendum - 2026-06-08

The scheduler-state evidence used to create the first runtime map is now historical, not current.

Fresh read-only reconciliation exists at `sellerone_manager/CONTROL/SO21_SCHEDULER_STATE_RECONCILIATION.md`.

Plain-English meaning:

- the classification model below is still useful
- the old "all visible tasks disabled" state must not be treated as current truth
- future maintenance planning must use the reconciliation report before making any decision
- no scheduler change is approved by this addendum

The fresh reconciliation found:

- most mapped SellerOne scheduled tasks are currently `Ready`
- `AMZ Restart Postcheck` and `Codex_H_Phase1_OneShot` are currently `Disabled`
- one extra visible SellerOne/Codex-related task, `CodexHProbe_20260327_005911`, is not in the original 11-task map

Until reviewed, `CodexHProbe_20260327_005911` is classified as `Maintenance Protected`.

## Runtime Categories

### Business Runtime

Business Runtime means a task appears connected to live selling work, pricing, orders, scanner cycles, H/O/A/B/F flow work, or restart chains.

Rules:

- Do not pause automatically.
- Do not restart automatically.
- Any pause, restart, enable, disable, edit, delete, or replacement requires explicit Luke approval.
- A future maintenance tool may only touch these tasks after a named approved maintenance packet says exactly what is allowed.

### Control Desk Automation

Control Desk Automation means a task appears connected to reporting, MOT checks, Rep briefing, health checks, usage reports, cleanup reports, or queue visibility.

Rules:

- May be designed for future Operations-managed pause or restart.
- Current Windows scheduled-task changes still require explicit approval before use.
- Must write control evidence only.
- Must not perform protected business work.

### Maintenance Protected

Maintenance Protected means the task is unknown, legacy, one-shot, installer-like, scheduler-control-related, or not safe to classify as pauseable.

Rules:

- Do not touch until reviewed.
- Do not pause automatically.
- Do not restart automatically.
- Requires classification and explicit Luke approval before any future maintenance tool can manage it.

## Visible Windows Scheduled Task Map

The tasks below are the visible Windows scheduled tasks recorded in the existing scheduler review evidence.

| Name | Purpose | Classification | Owner | Can Pause | Can Restart | Requires Luke Approval | Notes |
|---|---|---|---|---|---|---|---|
| `AMZ Controlled Restart` | Appears to control or trigger a SellerOne/Amazon restart chain. | Business Runtime | Windows Task Scheduler / SellerOne runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | ADR-0019 records Luke approved a temporary pause for this task during 2.1 stabilisation. Do not re-enable without a new approval. |
| `AMZ H Cycle` | Appears to run the H cycle. | Business Runtime | Windows Task Scheduler / H runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | H runtime can affect business flow evidence. Treat as protected business runtime. |
| `AMZ Morning MOT Post A` | Appears to run a morning MOT check after A flow work. | Control Desk Automation | Windows Task Scheduler / MOT control evidence | Future design may allow Operations pause after approval. | Future design may allow Operations restart after approval. | Yes for any Windows scheduler change. | Control evidence only. Must not become a hidden A runner. |
| `AMZ Morning MOT Post Restart` | Appears to run a morning MOT check after restart-chain activity. | Control Desk Automation | Windows Task Scheduler / MOT control evidence | Future design may allow Operations pause after approval. | Future design may allow Operations restart after approval. | Yes for any Windows scheduler change. | Control evidence only. Must not restart runtime itself unless separately approved. |
| `AMZ Orders` | Appears connected to Amazon order processing or order evidence. | Business Runtime | Windows Task Scheduler / Orders runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | Orders are protected business work. Do not touch without Luke approval. |
| `AMZ Price List Manager` | Appears connected to price-list management. | Business Runtime | Windows Task Scheduler / Pricing runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | Price-related tasks are protected because price changes require Luke approval. |
| `AMZ Pricing Summary` | Appears connected to pricing summary evidence or reporting. | Business Runtime | Windows Task Scheduler / Pricing runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | Even if summary-only, keep price-related tasks under Business Runtime until reviewed. |
| `AMZ Pricing Summary Hourly` | Appears connected to recurring pricing summary evidence or reporting. | Business Runtime | Windows Task Scheduler / Pricing runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | Not listed in ADR-0019's eight paused tasks, but visible in the scheduler review as disabled. Keep protected until reviewed. |
| `AMZ Restart Postcheck` | Appears to verify or follow the restart chain. | Business Runtime | Windows Task Scheduler / Restart-chain runtime | No automatic pause. Future pause only by approved maintenance packet. | No automatic restart. Future restart only by approved maintenance packet. | Yes | Restart-chain checks can affect runtime ownership and proof timing. Keep protected. |
| `Codex_H_Phase1_OneShot` | Appears to be a legacy one-shot H-related task. | Maintenance Protected | Windows Task Scheduler / legacy H maintenance | No. | No. | Yes | One-shot and legacy-style scheduler tasks must not be touched until their purpose is reviewed. |
| `CodexHProbe_20260327_005911` | Extra visible SellerOne/Codex-related scheduled task found during read-only scheduler reconciliation. | Maintenance Protected | Windows Task Scheduler / unknown legacy probe | No. | No. | Yes | Not in the original 11-task runtime map. Treat as unmapped and protected until a separate classification packet reviews it. |
| `SellerOne Manager Hourly MOT` | Appears to run hourly Manager MOT control reporting. | Control Desk Automation | Windows Task Scheduler / SellerOne Manager control desk | Future design may allow Operations pause after approval. | Future design may allow Operations restart after approval. | Yes for any Windows scheduler change. | ADR-0019 records Luke approved a temporary pause for this task during 2.1 stabilisation. Do not re-enable without a new approval. |

## Codex Automation Boundary

Codex app automations are a separate layer from Windows scheduled tasks.

Current control evidence says old Codex app automations should not be resumed blindly. They should be retired or rebuilt from the 2.1 control model.

Rules:

- Old Codex automation IDs are not runtime-control approval.
- New automations should be created paused first.
- Activation of any recurring automation requires explicit approval for the exact pilot behavior.
- Codex automations must write control evidence only unless a protected packet explicitly approves more.

## Enter Maintenance Design

This is a future process design only. No script exists or is approved by this document.

1. Request maintenance.
   - The request must name the target flow, expected duration, affected files or outputs, and the reason maintenance is needed.
2. Check approval boundary.
   - If any Business Runtime or Maintenance Protected task could be affected, stop until Luke approves the exact action.
3. Verify safe state.
   - Check current control evidence, MOT state, locks, worker ownership, and active runtime warnings.
4. Create a maintenance record.
   - A future implementation should write a timestamped record showing who entered maintenance, why, and what is allowed.
5. Pause only approved items.
   - Business Runtime is not paused automatically.
   - Control Desk Automation may only be paused if the approved maintenance packet allows it.
   - Maintenance Protected items are never paused by default.
6. Run worker activity inside the approved scope.
   - The worker must stay inside the packet and avoid protected actions.
7. Preserve rollback evidence.
   - Any future implementation must preserve scheduler export or state evidence before changing anything.

## Exit Maintenance Design

This is a future process design only. No script exists or is approved by this document.

1. Verify work completed.
   - Confirm the worker's isolated verification passed.
2. Check whether runtime was changed.
   - If no runtime was paused, do not restart anything just because maintenance is ending.
3. Restart only approved items.
   - Never restart Business Runtime or Maintenance Protected tasks without explicit approval.
   - Restart only the items listed in the approved maintenance record.
4. Run health checks.
   - Use the named proof route from the packet.
   - Separate `isolated verification passed` from `live loop verification confirmed`.
5. Record maintenance end.
   - A future implementation should write end time, final status, proof paths, and unresolved follow-ups.
6. Record deferred proof if needed.
   - If runtime proof needs time to appear, write the trigger, target artifact, success criteria, and remediation path into a durable tracking file before ending the worker turn.

## Future Script Ideas

These are design ideas only. They are not approved to build or use.

| Future Script | Purpose | Approval Required Before Build | Approval Required Before Use | Notes |
|---|---|---:|---:|---|
| `runtime_status.bat` | Read-only status summary for scheduler, locks, workers, and control evidence. | Yes | Yes | Should be read-only and safe to run without changing runtime after approval. |
| `enter_maintenance.bat` | Future controlled entry into maintenance mode. | Yes | Yes | Must refuse protected actions unless the packet explicitly allows them. |
| `exit_maintenance.bat` | Future controlled exit from maintenance mode. | Yes | Yes | Must restart only what the approved maintenance record says was paused. |
| `runtime_control_report.py` | Future readable report generator for this control map. | Yes | Yes | Should read evidence and write a report only. |

## Future Approval Requirements

The following future actions require explicit Luke approval before they are built or used:

- Pausing, enabling, disabling, editing, deleting, creating, or restarting any Windows scheduled task.
- Re-enabling any task paused during SellerOne 2.1 stabilisation.
- Restarting any worker, service, runtime loop, or business flow.
- Creating a maintenance script that can change scheduler or runtime state.
- Activating any recurring Codex automation.
- Allowing Operations to pause or restart any Control Desk Automation automatically.
- Touching price, order, stock, Product DB, local DB, Google Sheets, output deletion, Amazon login, or Amazon security paths.

## Stop Conditions

Stop and return to Rep if any future maintenance work would require:

- guessing about a business-critical task
- changing Windows Task Scheduler
- pausing runtime
- restarting services or workers
- implementing scripts
- changing queue state outside the approved packet
- touching prices, Sheets, databases, outputs, Amazon, or security state
- widening beyond the approved packet

## Verification

Planning evidence:

- This file exists at `sellerone_manager/CONTROL/RUNTIME_CONTROL.md`.
- All 11 visible Windows scheduled tasks from the existing scheduler review are classified.
- Runtime categories are defined.
- Enter-maintenance and exit-maintenance are documented as design only.
- Future implementation ideas are explicitly marked as not built and not approved for use.
- No runtime, scheduler, service, worker, automation, queue, price, Sheet, database, output, Amazon, or script implementation changes were made by this document.

## Current Next Move

Recommendation:

- continue with `SO21-RUNTIME-STATUS-READONLY-DESIGN` and `SO21-MAINTENANCE-RECORD-SPEC` before any pause/restart script implementation.
