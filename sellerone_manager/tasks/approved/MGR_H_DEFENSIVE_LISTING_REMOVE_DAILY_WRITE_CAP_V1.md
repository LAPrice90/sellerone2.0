# H Defensive Listing Remove Daily Write Cap v1

## Manager Authority
- task_id: MGR_H_DEFENSIVE_LISTING_REMOVE_DAILY_WRITE_CAP_V1
- job_ref: H-DEFENSIVE-NO-DAILY-CAP
- flow: H
- task_type: bounded_code_repair
- status: proved
- authority: luke_approved_live_behavior_correction
- priority: high
- luke_action_required: 0

## Plain English
The B06 defensive listing strategy was meant to keep pressuring a lower rival inside floor and ceiling. A daily write cap was added during implementation and caused H to stop trying after two accepted writes even though the competitor stayed below us. This packet removes that cap from H defensive listing behavior.

## Allowed Work
- remove the defensive listing daily write cap logic
- remove the cap column from the B06 defensive config
- add focused tests proving old daily write memory cannot block a defensive undercut
- run read-only H MOT after the code/test repair

## Forbidden Work
- no manual H run
- no scheduler ownership change
- no manual price change
- no publish action
- no queue edit
- no Google Sheets write
- no local DB alignment
- no output deletion
- no worker restart

## Acceptance Proof
- `max_writes_per_day` is not present in the live B06 defensive config.
- H defensive listing code has no `daily_write_limit` hold branch.
- Focused tests prove B06 still undercuts when the rival is below us even if old memory says many writes happened today.
- Live proof remains pending until a normal H-owned run loads the updated code.

## Retest
- retest_command: python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q

## Stop Condition
Stop before any manual price, H run, publish, scheduler, queue, Sheet, DB, output deletion, or restart action.
