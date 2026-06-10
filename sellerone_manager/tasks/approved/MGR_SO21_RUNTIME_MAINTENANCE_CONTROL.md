# SO21 Runtime Maintenance Control

## Manager Authority
- task_id: MGR_SO21_RUNTIME_MAINTENANCE_CONTROL
- job_ref: SO21-RUNTIME-MAINTENANCE-CONTROL
- flow: SO21
- task_type: planning_only_runtime_control
- status: proved
- authority: luke_approved_planning_ticket
- priority: high
- luke_action_required: 0

## Plain English
SellerOne needs a safe maintenance-mode design so workers can understand runtime risk before doing maintenance work.

Right now, Windows Task Scheduler jobs sit outside the SellerOne control model. That means workers do not have a central map showing which scheduled tasks are business-critical, which are control-desk automations, and which are unknown or protected. This ticket creates the planning document only. It does not pause, restart, disable, edit, or delete anything.

## Business Reason
Luke needs a controlled way to plan maintenance without manually hunting through Windows Task Scheduler every time.

The system should know:

- what can be paused
- what must never be paused automatically
- how maintenance mode should be requested
- how maintenance mode should exit
- how recovery should work if maintenance fails

## Current Problem
- Task Scheduler jobs live outside the SellerOne control system.
- Workers do not know which jobs are safe to stop.
- Workers do not know which jobs are business-critical.
- There is no central runtime control document.
- Active scheduled tasks may overwrite files, restart processes, read half-finished outputs, create false health failures, or interfere with testing.

## Desired Outcome
Create a planning-only Runtime Control Layer.

Every scheduled task should be classified as one of:

- `Business Runtime`
- `Control Desk Automation`
- `Maintenance Protected`

## Allowed Work
- inspect scheduled-task metadata and existing control files
- classify scheduled tasks in a human-readable runtime map
- create `CONTROL/RUNTIME_CONTROL.md`
- document runtime categories
- design the maintenance-mode process
- document future script ideas only
- identify which future steps require Luke approval

## Forbidden Work
- no business runtime stops
- no scheduled-task disable, enable, edit, delete, or restart
- no Task Scheduler modification
- no service restart
- no worker restart
- no Codex automation changes
- no queue movement beyond this planning packet
- no price changes
- no Google Sheets writes
- no Product DB or local DB alignment
- no output deletion
- no Amazon login or security action
- no implementation of maintenance scripts

## Required Deliverable
Create:

- `sellerone_manager/CONTROL/RUNTIME_CONTROL.md`

The document must include, for each scheduled task:

- name
- purpose
- classification
- owner
- can pause
- can restart
- requires Luke approval
- notes

## Runtime Categories
### Business Runtime
Examples:

- Orders
- Pricing
- F Scanner
- H Runtime
- Restart Chain

Rules:

- normally always running
- cannot be stopped automatically
- requires Luke approval

### Control Desk Automation
Examples:

- Rep briefing
- health watchers
- reporting
- cleanup reports
- usage reports

Rules:

- safe to pause when approved by Operations rules
- safe to restart when approved by Operations rules
- may be managed by Operations

### Maintenance Protected
Examples:

- unknown tasks
- legacy tasks
- unclassified tasks

Rules:

- never touched until reviewed
- requires classification before future maintenance automation

## Maintenance Mode Design
Document the future process for:

### Enter Maintenance
1. Request maintenance.
2. Verify safe state.
3. Pause only approved runtime/control items.
4. Record maintenance start.
5. Allow worker activity.

### Exit Maintenance
1. Verify work completed.
2. Restart only approved runtime/control items.
3. Run health checks.
4. Record maintenance end.

## Future Scripts
Design only. Do not build yet.

Potential future tools:

- `enter_maintenance.bat`
- `exit_maintenance.bat`
- `runtime_status.bat`

## Acceptance Proof
- `CONTROL/RUNTIME_CONTROL.md` exists.
- All visible scheduled tasks are classified.
- Runtime categories are defined.
- Enter-maintenance and exit-maintenance processes are documented.
- Future implementation approach is described as design only.
- No runtime changes occurred during this ticket.
- Any future pause/restart implementation is marked as needing explicit approval before build or use.

## Retest
- retest_command: Inspect `CONTROL/RUNTIME_CONTROL.md` and confirm no Task Scheduler state changed.

## Stop Condition
Stop and return to Rep if classification would require guessing about a business-critical task, changing Task Scheduler, pausing runtime, restarting services, implementing scripts, or widening beyond planning and classification.
