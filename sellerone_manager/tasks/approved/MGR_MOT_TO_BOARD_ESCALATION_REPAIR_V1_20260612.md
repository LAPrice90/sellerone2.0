# MOT To Board Escalation Repair V1

Job ref: `MOT-TO-BOARD-ESCALATION-REPAIR-V1`

## Purpose

Repair the management gap where MOT warnings exist but the board does not keep urgent business risks visible.

## Business Reason

The A2-T2AC-TW3L issue showed that a warning can exist in MOT evidence while the board still parks the job. That defeats the point of a manager.

## Scope

Code and test repair only.

Allowed:

- inspect MOT output fields
- inspect board update logic
- add escalation rules for money/risk/runtime warnings
- add tests or proof examples

## Required Output

Write:

`CONTROL/MOT_TO_BOARD_ESCALATION_REPAIR_V1_RESULT_20260612.md`

The result must prove:

- MOT warnings that affect money become active board risks
- blocked pricing/floor states are not parked as ready later
- board status follows business risk, not report completion

## Forbidden Actions

Do not:

- change prices
- edit token ledgers
- write Google Sheets
- edit queues
- edit Product DB or local DB facts
- restart runtime
- modify Task Scheduler
- call Amazon
- delete outputs

