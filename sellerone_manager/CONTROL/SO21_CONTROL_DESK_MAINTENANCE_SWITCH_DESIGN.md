# SO21 Control Desk Maintenance Switch Design

Job: `SO21-CONTROL-DESK-MAINTENANCE-SWITCH-DESIGN`
Created: 2026-06-08
Mode: planning only

## Plain-English Purpose

This document designs a future maintenance switch for read-only control-desk automations only.

Think of it like a labelled light switch for the office notice board, not the main power for the shop. It may eventually let Operations pause or resume reporting, briefing, MOT, cleanup, or queue-visibility automation during maintenance. It must not pause, restart, kill, edit, or manage the live selling runtime.

This document does not implement or use a pause/resume switch.

## Source Documents

This design depends on:

- `sellerone_manager/CONTROL/RUNTIME_CONTROL.md`
- `sellerone_manager/CONTROL/SO21_RUNTIME_STATUS_READONLY_DESIGN.md`
- `sellerone_manager/CONTROL/SO21_MAINTENANCE_RECORD_SPEC.md`
- `sellerone_manager/CONTROL/SO21_MAINTENANCE_MODE_IMPLEMENTATION_PLAN.md`
- `sellerone_manager/CONTROL/SO21_BUSINESS_RUNTIME_MAINTENANCE_AUTHORITY.md`
- `sellerone_manager/CONTROL/RUNTIME_SAFETY_RULES.md`
- `sellerone_manager/CONTROL/OPERATIONS.md`

The key dependency is `SO21_MAINTENANCE_RECORD_SPEC.md`.

Restart must come from the maintenance record, not memory. If a target was not recorded as paused, the future switch must not resume it.

## Scope

Allowed future target class:

- Control Desk Automation

Examples of possible future control-desk targets:

- Rep briefing pilot automation
- MOT report automation
- queue visibility report automation
- cleanup monitor automation
- read-only operations report automation

Refused target classes:

- Business Runtime
- Maintenance Protected
- unknown or unmapped target

This design does not approve Windows Task Scheduler edits, Codex automation mutation, business runtime work, or any process control. It only defines what a reviewed future implementation would have to prove before any action.

## Non-Negotiable Rule

The control-desk maintenance switch must never become a business-runtime switch.

If a target affects orders, pricing, scanner cycles, H/O/A/B/F flow work, restart chains, Amazon login/security, Product DB, local DB facts, Google Sheets, stock, receiving, purchasing, or send-to-Amazon work, the future switch must refuse it.

## Required Future Input

A future pause or resume request must provide all of these before action:

- maintenance request record id
- maintenance record id
- job reference
- named target
- target classification
- reason for maintenance
- requested action: pause or resume
- expected duration
- exact restart route
- post-restart proof route
- approval source
- owner responsible for the maintenance record
- stop conditions

If any required field is missing, the future switch must refuse the action and write a blocker record instead of guessing.

## Preflight Checks

Before any future control-desk pause, the switch must:

1. Read the maintenance request.
2. Read the active maintenance record.
3. Confirm the target is listed as Control Desk Automation in current control evidence.
4. Confirm the target is not Business Runtime.
5. Confirm the target is not Maintenance Protected.
6. Confirm the target is not unknown or unmapped.
7. Confirm the requested action is named exactly.
8. Confirm the restart route is named before pause.
9. Confirm the proof route is named before pause.
10. Check current read-only runtime status evidence.
11. Check for active maintenance records that conflict with this target.
12. Check for locks or worker ownership warnings.
13. Check the overnight or proof-window timing rule if applicable.

If any check fails, the future switch must refuse and record why.

## Allowed Future Pause Behavior

For a valid Control Desk Automation target only, a future reviewed switch may pause using the safest target-specific route approved in the maintenance record.

The pause record must capture:

- time paused
- target paused
- action method
- previous observed state
- owner
- reason
- expected resume condition
- restart route
- proof route
- rollback path

The future switch must not pause anything that is not named in the record.

## Allowed Future Resume Behavior

For a valid Control Desk Automation target only, a future reviewed switch may resume only if the active maintenance record says that exact target was paused.

The resume record must capture:

- time resumed
- target resumed
- resume method
- target state before resume
- target state after resume
- proof route triggered
- proof result or pending proof condition
- unresolved follow-ups
- remediation path if proof fails

The future switch must not resume a target just because it exists, looks disabled, or was probably paused earlier.

## Refusal Rules

The future switch must refuse Business Runtime targets.

Business Runtime refusal message should include:

- target name
- observed classification
- requested action
- reason refused
- required path: separate approved maintenance record with exact business-runtime authority

The future switch must refuse Maintenance Protected targets.

Maintenance Protected refusal message should include:

- target name
- observed classification
- requested action
- reason refused
- required path: separate classification or approval packet before any action

The future switch must refuse unknown targets.

Unknown target refusal message should include:

- target name
- requested action
- reason refused
- required path: add or update runtime classification evidence first

The future switch must also refuse:

- process kill
- hard kill
- worker restart
- Task Scheduler enable, disable, edit, create, delete, or restart
- Codex automation mutation without exact approval
- queue edits outside approved task status updates
- price changes
- Google Sheets writes
- database writes or alignment
- output deletion, movement, compression, purge, archive apply, or rename
- Amazon login/security action
- purchase, receiving, or send-to-Amazon action

## Recording Rules

Every future pause/resume attempt must write durable evidence, even if refused.

The record must include:

- record id
- created time
- job reference
- target
- classification
- requested action
- result: refused, paused, resumed, blocked, or no-op
- reason
- approval source
- operator or owner
- exact method used, if any
- proof route, if any
- blocker details, if any

Refused actions must not be hidden as warnings. They are a control result.

## Proof Routes

The future switch must require a named proof route before pause.

Acceptable proof route examples for control-desk targets:

- read-only status report shows target state changed as expected
- next scheduled control report appears at the expected path
- automation heartbeat or run evidence is fresh
- maintenance exit record shows health check completed
- Operations report records target resumed and proof passed

Proof must separate:

- `pause recorded`
- `resume recorded`
- `read-only status confirmed`
- `post-restart proof passed`

If proof depends on a future scheduled run, the follow-up must be written into a durable tracking file with:

- exact trigger or time to check
- target file or output to inspect
- expected success criteria
- remediation path if it fails

## Blocker Behavior

If the future switch hits Windows permissions, locked files, Task Scheduler access limits, missing credentials, app connector limits, machine-level restrictions, or a protected-boundary conflict, it must stop and write a blocker.

The blocker must include:

- affected job
- what was attempted
- what failed
- evidence or error summary
- safest proposed fix
- whether Luke approval is needed

It must not retry blindly, guess, skip silently, or widen scope.

## Timing Rule

During the 2026-06-08 overnight control test window, no future check should be started after 2026-06-09 01:45 UK if it could be interrupted by the expected 02:00 UK restart.

If a proof wait crosses a restart or cooling-off period, the follow-up must be written durably before the worker turn ends.

## Future Implementation Boundary

This design may support a future reviewed implementation, but that implementation is not approved here.

Before building or using any state-changing switch, a new approved packet must define:

- exact file or tool to build
- exact allowed target list
- exact record folder
- exact proof command or review route
- rollback behavior
- refusal tests
- reviewer acceptance proof

## Acceptance Proof For This Design

This planning document satisfies the packet when:

- this file exists at `sellerone_manager/CONTROL/SO21_CONTROL_DESK_MAINTENANCE_SWITCH_DESIGN.md`
- the design is limited to Control Desk Automation
- the design refuses Business Runtime targets
- the design refuses Maintenance Protected targets
- the design depends on `SO21_MAINTENANCE_RECORD_SPEC.md`
- the design requires named target, reason, exact restart route, and post-restart proof route before future action
- the design does not implement or use a pause/resume switch

## State Change Statement

No runtime, scheduler, process, worker, automation, queue, price, Sheet, database, output, Amazon/security, purchase, receiving, send-to-Amazon, deletion, movement, compression, purge, archive, rename, or state-changing maintenance-script action is performed by this document.

## Current Next Move

Recommendation:

- review this design against the approved packet, then decide whether a separate future build packet should implement a read-only validated control-desk maintenance tool.
