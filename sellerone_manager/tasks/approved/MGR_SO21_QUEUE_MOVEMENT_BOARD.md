# SO21 Queue Movement Board

## Manager Authority
- task_id: MGR_SO21_QUEUE_MOVEMENT_BOARD
- job_ref: SO21-QUEUE-MOVEMENT-BOARD
- flow: SO21
- task_type: control_visibility
- status: proved
- authority: first_overnight_run_efficiency_plan_2026-06-09
- priority: high
- luke_action_required: 0

## Plain English
The current queue shows job stage, but not whether the job is genuinely moving.

This task creates a plain-English movement board so Luke and Operations can see job age, last real movement, owner role, next action, and blocker reason.

## Allowed Work
- inspect current tickets, approved packet index, task packets, review notes, and control evidence
- separate board refresh timestamps from real job movement timestamps
- create `CONTROL/SO21_QUEUE_MOVEMENT_BOARD.md`
- recommend any missing movement fields needed for future queue generation

## Forbidden Work
- no implementation changes
- no business runtime changes
- no Task Scheduler changes
- no process kill
- no worker restart
- no Amazon/security action
- no price, Sheet, database, purchase, receiving, or send-to-Amazon action
- no deletion, movement, compression, purge, archive apply, or cleanup apply
- no queue status movement except reporting evidence

## Acceptance Proof
- `CONTROL/SO21_QUEUE_MOVEMENT_BOARD.md` exists.
- It shows active SO21 jobs with stage, last real movement, owner role, age/idle risk, next action, and blocker if present.
- It identifies where timestamps are currently too weak or polluted by board refreshes.
- It recommends a safe next improvement without changing runtime or business data.

## Retest
- retest_command: inspect the movement board and confirm it is visibility-only.

