# SO21 Active System Service MOT

## Manager Authority
- task_id: MGR_SO21_ACTIVE_SYSTEM_SERVICE_MOT
- job_ref: SO21-ACTIVE-SYSTEM-SERVICE-MOT
- flow: SO21
- task_type: management_system_review
- status: proved
- authority: luke_requested_full_service_before_moving_on
- priority: high
- luke_action_required: 0

## Plain English
Luke wants everything SellerOne is still using to get a service and MOT before moving on.

This should review the active management process, not every old file ever created.

## Allowed Work
- inspect active control files
- inspect active and blocked queue packets
- inspect Operations monitor rules
- inspect maintenance-mode planning evidence
- inspect read-only status and maintenance-record design
- inspect active control automations
- inspect worker/reviewer handoff model
- identify bugs, fragile assumptions, process confusion, and efficiency improvements
- write a plain-English report under `CONTROL/`
- recommend tomorrow's fix order

## Forbidden Work
- no implementation changes
- no runtime pause or restart
- no process kill
- no Task Scheduler change
- no worker restart
- no Amazon login/security action
- no price, Sheet, database, output, purchase, receiving, or send-to-Amazon action
- no permanent deletion

## Acceptance Proof
- `CONTROL/SO21_ACTIVE_SYSTEM_SERVICE_MOT_PLAN.md` exists.
- A plain-English MOT report is created under `CONTROL/`.
- Findings are grouped by decision, risk, and improvement.
- No protected action occurred.

## Retest
- retest_command: Inspect the MOT report and confirm it is review-only.

## Stop Condition
Stop before implementation or protected action.
