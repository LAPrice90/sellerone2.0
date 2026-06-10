# F Cycle Backtest - Execution Batch 4

## Purpose

This batch switches the already-built backtest into the repo's new active planning flow.

It is a tracking and continuity batch.

It is not a model-change batch.

## Batch Goal

Move the durable memory for the backtest from:
- reference notes only

to:
- an active plan folder under `plans/active/`
- with current status, runbook, contracts, and carried-forward execution history

## Important Batch Rule

Do not change:
- replay math
- recommendation logic
- health-check logic
- policy values
- runtime ownership

Only do:
- active plan workspace creation
- source batch/history migration
- current-state write-up
- next continuation-point definition

## Task 1 - Create Active Plan Workspace

### Goal

Create a standard active plan folder for the backtest.

### Required implementation

Use:
- `scripts/one_off/P001_create_plan_workspace.py`

Target slug:
- `f-cycle-backtest-v1`

### Acceptance criteria

- `plans/active/f-cycle-backtest-v1/` exists
- standard plan files exist

## Task 2 - Copy Existing Plan History

### Goal

Bring the real source plan and execution batches into the active plan folder.

### Required implementation

Copy in:
- coding plan
- execution batches 001 to 003
- execution batch replies 001 to 003
- working notes source

### Acceptance criteria

- future sessions can inspect execution history from the active plan folder
- original reference files remain unchanged

## Task 3 - Write Current Status Files

### Goal

Replace template placeholders with the actual backtest state.

### Required implementation

Write:
- `PROJECT_BRIEF.md`
- `PLAN.md`
- `PLAN_STATUS.md`
- `DATA_CONTRACTS.md`
- `RUNBOOK.md`

### Required content

Must state:
- what is already complete
- what proof exists
- what still is not yet tracked centrally
- what the next continuation point should be

### Acceptance criteria

- no template placeholders remain in the written status files
- status reflects Batch 001 to 003 as complete

## Task 4 - Capture Proof Snapshot

### Goal

Record the current proof position without rerunning unrelated systems.

### Required implementation

Use existing artifacts to capture:
- output row counts
- latest backtest health status
- latest calibration-pack status
- current global health snapshot status

### Acceptance criteria

- plan status contains a factual evidence block
- no ad-hoc A script run is used

## Expected End State

This batch is complete when:
- the backtest has an active plan folder
- the plan folder contains the real execution trail
- the current state is written clearly enough to resume in a fresh session

## Not In This Batch

Do not do these here:
- Batch 005 feature work
- roadmap score inflation
- WORK_LOG append without explicit user approval

## Suggested Final Output Back To User

When this batch is done, report:
- where the plan really is
- what was switched into the new flow
- what remains to define before the next code batch
