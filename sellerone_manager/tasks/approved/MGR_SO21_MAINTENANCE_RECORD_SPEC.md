# SO21 Maintenance Record Spec

## Manager Authority
- task_id: MGR_SO21_MAINTENANCE_RECORD_SPEC
- job_ref: SO21-MAINTENANCE-RECORD-SPEC
- flow: SO21
- task_type: maintenance_mode_design
- status: proved
- authority: luke_expanded_tonight_control_authority
- priority: high
- luke_action_required: 0

## Plain English
Maintenance mode needs a written record for every session.

That record is what prevents confusion about what was paused, why it was paused, how it should restart, and what proof is needed before calling the work safe.

## Allowed Work
- design the maintenance request record
- design the active maintenance record
- design the exit record
- define required fields such as job reference, target cycle, approval source, pause method, restart method, proof route, and rollback path
- write planning evidence under `CONTROL/`

## Forbidden Work
- no runtime pause
- no process kill
- no restart
- no Task Scheduler change
- no script implementation that changes state
- no worker restart
- no Codex automation mutation
- no price, Sheet, database, output, queue, Amazon, or security action

## Acceptance Proof
- A maintenance record specification exists under `CONTROL/`.
- It defines request, active, and exit records.
- It requires restart to come from the record, not memory.
- It keeps business runtime approval-gated.
- No runtime or scheduler change occurred.

## Retest
- retest_command: Inspect the maintenance record spec and confirm it is planning only.

## Stop Condition
Stop before implementing any state-changing maintenance tool.
