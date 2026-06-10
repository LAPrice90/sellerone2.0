# SO21 Script Status Health Map

## Manager Authority
- task_id: MGR_SO21_SCRIPT_STATUS_HEALTH_MAP
- job_ref: SO21-SCRIPT-STATUS-HEALTH-MAP
- flow: SO21
- task_type: maintenance_status_planning
- status: proved
- authority: luke_requested_script_status_maintenance
- priority: high
- luke_action_required: 0

## Plain English
Luke wants SellerOne to know whether important scripts are healthy without manually checking Task Scheduler or output folders.

This ticket creates a health map for scripts and checks. It is read-only planning.

## Allowed Work
- inspect current control files and scheduler evidence
- identify active scripts and launchers
- list expected proof outputs
- define stale/fail thresholds
- recommend owner and repair route
- write a script health map under `CONTROL/`

## Forbidden Work
- no Task Scheduler changes
- no runtime pause or restart
- no process kill
- no worker restart
- no script implementation
- no deletion or output cleanup
- no Amazon/security
- no prices, Sheets, databases, purchases, receiving, or send-to-Amazon

## Acceptance Proof
- A script health map exists under `CONTROL/`.
- It lists script/check purpose, owner, proof output, stale threshold, and repair route where known.
- It is read-only and does not change scheduler or runtime state.

## Retest
- retest_command: Inspect the script health map and confirm no state changes occurred.

## Stop Condition
Stop before any state-changing maintenance action.
