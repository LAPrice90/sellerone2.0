# SO21 Overnight Control Test Plan

## Manager Authority
- task_id: MGR_SO21_OVERNIGHT_CONTROL_TEST_PLAN
- job_ref: SO21-OVERNIGHT-CONTROL-TEST-PLAN
- flow: SO21
- task_type: overnight_control_test_plan
- status: proved
- authority: luke_requested_overnight_quiet_tests
- priority: high
- luke_action_required: 0

## Plain English
Luke requested overnight tests while the PC is quiet, with awareness that the PC restarts at 02:00 UK.

This packet defines safe control-layer tests only. It does not approve runtime, scheduler, process, Amazon, price, Sheet, database, output, purchase, receiving, or send-to-Amazon actions.

## Allowed Work
- create `CONTROL/SO21_OVERNIGHT_CONTROL_TEST_PLAN.md`
- define safe overnight read-only checks
- define pre-restart stop timing
- define post-restart recovery check
- hand the plan to Operations

## Forbidden Work
- no process kill
- no business runtime pause or restart
- no Task Scheduler change
- no worker restart
- no Amazon login/security
- no prices
- no Google Sheets writes
- no database writes or alignment
- no output deletion
- no purchase, receiving, or send-to-Amazon
- no state-changing maintenance scripts

## Acceptance Proof
- `CONTROL/SO21_OVERNIGHT_CONTROL_TEST_PLAN.md` exists.
- The plan references the expected 02:00 UK restart on 2026-06-09.
- Tests are read-only or planning/control only.
- Protected actions remain blocked.

## Retest
- retest_command: Inspect the overnight test plan and confirm it is read-only/control-only.

## Stop Condition
Stop before any protected runtime, scheduler, process, worker, Amazon/security, price, Sheet, database, output, purchase, receiving, send-to-Amazon, deletion, or state-changing maintenance action.
