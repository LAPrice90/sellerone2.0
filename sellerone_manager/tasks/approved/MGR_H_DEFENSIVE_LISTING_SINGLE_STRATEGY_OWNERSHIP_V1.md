# H Defensive Listing Single Strategy Ownership v1

## Manager Authority
- task_id: MGR_H_DEFENSIVE_LISTING_SINGLE_STRATEGY_OWNERSHIP_V1
- job_ref: H-DEFENSIVE-SINGLE-STRATEGY
- flow: H
- task_type: bounded_code_repair
- status: proved
- authority: luke_approved_live_behavior_correction
- priority: high
- luke_action_required: 0

## Plain English
B06 defensive listing protection was letting normal H take the SKU back after defensive mode had already put us 1p under the rival. That meant two strategies were fighting over one SKU. This packet makes defensive listing protection the single controlling strategy while the rival is present.

## Allowed Work
- edit H defensive listing ownership logic
- edit the H caller only if it passes the wrong proof into the guard
- update H MOT manager proof for the new ownership rule
- add focused tests proving B06 stays under defensive ownership while the rival is present
- run focused tests, compile checks, and read-only H MOT

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
- If the rival is equal to us during the pressure window, defensive mode owns the SKU and may undercut by 1p.
- If we are already 1p under the rival, defensive mode owns the SKU and holds that position with no write.
- If the rival is above us during the pressure window, defensive mode owns the SKU and does not let normal H raise us.
- Manager MOT fails future proof that hands B06 back to normal H while the rival is present.
- Live proof remains pending until a fresh H-owned run loads the updated code.

## Retest
- retest_command: python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H

## Stop Condition
Stop before any manual price, H run, publish, scheduler, queue, Sheet, DB, output deletion, or restart action.
