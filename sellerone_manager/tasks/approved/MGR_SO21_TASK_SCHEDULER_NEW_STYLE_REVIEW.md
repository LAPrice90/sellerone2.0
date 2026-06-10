# SO21 Task Scheduler New-Style Review

## Manager Authority
- task_id: MGR_SO21_TASK_SCHEDULER_NEW_STYLE_REVIEW
- job_ref: SO21-TASK-SCHEDULER-NEW-STYLE-REVIEW
- flow: SO21
- task_type: scheduler_style_review
- status: proved
- authority: luke_requested_task_scheduler_style_review
- priority: high
- luke_action_required: 0

## Plain English
Luke wants the Windows Task Scheduler list reviewed against the new SellerOne 2.1 management style.

This should say what still fits, what should become control-desk automation, what is business runtime, and what looks legacy or protected.

## Allowed Work
- inspect existing scheduler review evidence
- inspect read-only current scheduler metadata if needed
- compare tasks against `CONTROL/RUNTIME_CONTROL.md`
- classify each task into the new style
- recommend keep, redesign, retire-candidate, or protected-review
- write review under `CONTROL/`

## Forbidden Work
- no Task Scheduler enable, disable, edit, delete, create, or restart
- no runtime pause or restart
- no process kill
- no worker restart
- no script implementation
- no deletion
- no Amazon/security
- no prices, Sheets, databases, purchases, receiving, or send-to-Amazon

## Acceptance Proof
- A Task Scheduler new-style review exists under `CONTROL/`.
- Every visible SellerOne-related scheduled task is classified.
- Recommendations are review-only and do not change scheduler state.

## Retest
- retest_command: Inspect the scheduler review and confirm it is read-only.

## Stop Condition
Stop before any Task Scheduler or runtime change.
