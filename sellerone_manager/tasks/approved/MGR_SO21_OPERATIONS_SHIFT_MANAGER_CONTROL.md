# SO21 Operations Shift Manager Control

## Manager Authority
- task_id: MGR_SO21_OPERATIONS_SHIFT_MANAGER_CONTROL
- job_ref: SO21-OPERATIONS-SHIFT-MANAGER-CONTROL
- flow: SO21
- task_type: operations_control
- status: fixed_needs_retest
- authority: luke_approved_planning_ticket
- priority: high
- luke_action_required: 0

## Plain English
Operations is the shift-manager layer for SellerOne 2.1 control work.

It should not just watch tickets passively. It should manage the approved goal by monitoring progress, creating needed task packets, starting clean workers, arranging reviewers, and reporting blockers back to the Rep.

## Allowed Work
- create or update a clear Operations authority document under `CONTROL/`
- define what Operations may do for an approved goal
- define when Operations may create clean SellerOne 2.0 worker or reviewer threads
- define how Operations reports to the Rep
- define what Operations must never touch
- classify the active `SO21 Operations Cleanup Monitor` as an approved control-layer monitor if it matches Luke's stated model

## Forbidden Work
- no business runtime changes
- no Task Scheduler changes
- no price changes
- no Google Sheets writes
- no Product DB or local DB alignment
- no Amazon login or security action
- no file deletion, moving, compression, purging, archiving, or renaming
- no worker execution inside the Manager project
- no unrelated task creation
- no redesign beyond the Rep, Operations, Worker, Reviewer model

## Acceptance Proof
- A durable Operations control document exists under `CONTROL/`.
- The document states Operations can create tasks/workers/reviewers only inside an approved goal.
- The document states Operations cannot widen scope or touch protected areas.
- The document separates Business Runtime from Control Desk Automations.
- The active Operations monitor is either classified as approved or flagged for Rep/Luke decision.
- No protected action occurred.

## Retest
- retest_command: Inspect the Operations control document and `CONTROL/CURRENT_STATE.md`.

## Stop Condition
Stop if Operations authority would allow unapproved runtime work, unrelated task creation, or destructive cleanup without Luke approval.
