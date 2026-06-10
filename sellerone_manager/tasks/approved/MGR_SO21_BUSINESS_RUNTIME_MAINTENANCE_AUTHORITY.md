# SO21 Business Runtime Maintenance Authority

## Manager Authority
- task_id: MGR_SO21_BUSINESS_RUNTIME_MAINTENANCE_AUTHORITY
- job_ref: SO21-BUSINESS-RUNTIME-MAINTENANCE-AUTHORITY
- flow: SO21
- task_type: protected_decision
- status: proved
- authority: luke_approved_controlled_pause_restart_authority
- priority: normal
- luke_action_required: 0

## Plain English
Luke approved controlled pause/restart authority for maintenance mode on 2026-06-08.

This is not a blank kill switch. It allows a maintenance-record-based pause/restart model for named maintenance work.

## Decision Needed
Decision recorded:

Business runtime can be included in controlled maintenance pause/restart when the target, reason, restart route, approval source, and proof route are written into a maintenance record before action.

Examples:

- Orders
- Pricing
- F scanner
- H cycle
- restart chain

## Current Rule
Business Runtime remains controlled.

Operations and Workers may not perform blind kills or unrecorded pause/restart. Pause/restart must be tied to a named maintenance record and post-restart proof.

## Still Forbidden
- no blind process kill
- no permanent Task Scheduler change
- no unrecorded runtime pause
- no unrecorded runtime restart
- no unrecorded worker restart
- no price, Sheet, database, output, queue, Amazon, or security action

## Stop Condition
Stop before any pause/restart that does not have a named maintenance record, restart route, and proof route.
