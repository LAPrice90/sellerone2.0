# SO21 Runtime Status Read-Only Design

## Manager Authority
- task_id: MGR_SO21_RUNTIME_STATUS_READONLY_DESIGN
- job_ref: SO21-RUNTIME-STATUS-READONLY-DESIGN
- flow: SO21
- task_type: maintenance_mode_design
- status: proved
- authority: luke_expanded_tonight_control_authority
- priority: high
- luke_action_required: 0

## Plain English
Before SellerOne can safely pause or restart anything, it needs a read-only status view.

This is the "look at the breaker panel" step. It should show what appears to be running, paused, ready, blocked, or protected without changing anything.

## Allowed Work
- design the read-only runtime status view
- define what evidence it should read
- define what it must display for scheduler tasks, Codex automations, locks, worker ownership, and maintenance markers
- define warning messages when evidence is stale or mismatched
- write planning evidence under `CONTROL/`

## Forbidden Work
- no script that changes runtime state
- no Task Scheduler changes
- no process kill
- no restart
- no worker restart
- no Codex automation mutation
- no price, Sheet, database, output, queue, Amazon, or security action

## Acceptance Proof
- A design document exists under `CONTROL/`.
- The design is read-only.
- The design lists evidence inputs and protected boundaries.
- It explains how stale scheduler evidence is shown.
- It does not implement a pause, kill, restart, enable, disable, or scheduler edit.

## Retest
- retest_command: Inspect the read-only design and confirm it cannot change runtime state.

## Stop Condition
Stop before building or using any script that can change runtime, scheduler, worker, automation, business data, or Amazon/security state.
