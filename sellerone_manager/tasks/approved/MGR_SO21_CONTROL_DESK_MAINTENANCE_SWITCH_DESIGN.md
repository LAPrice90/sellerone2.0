# SO21 Control Desk Maintenance Switch Design

## Manager Authority
- task_id: MGR_SO21_CONTROL_DESK_MAINTENANCE_SWITCH_DESIGN
- job_ref: SO21-CONTROL-DESK-MAINTENANCE-SWITCH-DESIGN
- flow: SO21
- task_type: maintenance_mode_design
- status: proved
- authority: waits_for_runtime_status_and_record_spec
- priority: normal
- luke_action_required: 0

## Plain English
After runtime status and maintenance records are designed, SellerOne can design a safe maintenance switch for control-desk automations only.

This is not a business-runtime switch.

## Allowed Work
- design how Operations could pause and resume read-only control-desk automations
- define how each pause/resume action is recorded
- define refusal rules for business runtime and Maintenance Protected tasks
- write planning evidence under `CONTROL/`

## Forbidden Work
- no business runtime pause or restart
- no Task Scheduler change
- no process kill
- no worker restart
- no maintenance script implementation that changes runtime
- no price, Sheet, database, output, queue, Amazon, or security action

## Acceptance Proof
- A control-desk switch design exists under `CONTROL/`.
- It is limited to control-desk automations.
- It refuses Business Runtime and Maintenance Protected targets.
- It depends on the maintenance record spec.

## Retest
- retest_command: Inspect the design and confirm it cannot approve business runtime changes.

## Stop Condition
Stop before implementing or using a pause/resume switch.
