# SO21 Runtime Maintenance Control Review

## Manager Authority
- task_id: MGR_SO21_RUNTIME_MAINTENANCE_CONTROL_REVIEW
- job_ref: SO21-RUNTIME-MAINTENANCE-CONTROL-REVIEW
- flow: SO21
- task_type: reviewer_packet
- status: parked
- authority: waits_for_runtime_control_document
- priority: normal
- luke_action_required: 0

## Plain English
After `SO21-RUNTIME-MAINTENANCE-CONTROL` creates `CONTROL/RUNTIME_CONTROL.md`, a Reviewer should check the classification before SellerOne trusts it.

The review should confirm that business runtime is protected and that no maintenance-mode implementation was built early.

## Allowed Work
- inspect `CONTROL/RUNTIME_CONTROL.md`
- compare scheduled task classifications against available scheduler metadata
- verify Business Runtime, Control Desk Automation, and Maintenance Protected rules are clear
- verify enter-maintenance and exit-maintenance designs are planning-only
- report gaps or approval needs

## Forbidden Work
- no Task Scheduler changes
- no runtime pause or restart
- no service restart
- no script implementation
- no queue movement unless review proof rules allow it
- no price, Sheet, database, output deletion, or Amazon changes

## Acceptance Proof
- Reviewer confirms all visible scheduled tasks are classified or explicitly marked unknown/protected.
- Reviewer confirms no runtime changes occurred.
- Reviewer confirms future scripts remain design-only.
- Reviewer returns exact gaps if the runtime map is not safe enough.

## Retest
- retest_command: Inspect `CONTROL/RUNTIME_CONTROL.md` and current scheduler metadata without changing scheduler state.

## Stop Condition
Stop if review would require changing Task Scheduler, pausing runtime, restarting services, or implementing maintenance scripts.
