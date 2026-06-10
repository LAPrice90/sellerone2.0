# SO21 New-Style Script Monitoring Design

## Manager Authority
- task_id: MGR_SO21_NEW_STYLE_SCRIPT_MONITORING_DESIGN
- job_ref: SO21-NEW-STYLE-SCRIPT-MONITORING-DESIGN
- flow: SO21
- task_type: monitoring_design
- status: parked
- authority: waits_for_script_health_map_and_scheduler_review
- priority: normal
- luke_action_required: 0

## Plain English
After the script health map and Task Scheduler review exist, SellerOne should design the new-style monitoring system.

The goal is to replace scattered checking with one control-desk health view.

## Allowed Work
- design read-only script health monitoring
- define Operations summary format
- define stale/fail/blocker handling
- define when maintenance mode is needed
- define when Luke is needed
- write design under `CONTROL/`

## Forbidden Work
- no monitor implementation yet
- no Task Scheduler changes
- no runtime pause or restart
- no process kill
- no worker restart
- no deletion
- no Amazon/security
- no prices, Sheets, databases, purchases, receiving, or send-to-Amazon

## Acceptance Proof
- A monitoring design exists under `CONTROL/`.
- It depends on the script health map and scheduler new-style review.
- It stays read-only/design-only.

## Retest
- retest_command: Inspect the design and confirm it is not an implementation.

## Stop Condition
Stop before implementation or protected action.
