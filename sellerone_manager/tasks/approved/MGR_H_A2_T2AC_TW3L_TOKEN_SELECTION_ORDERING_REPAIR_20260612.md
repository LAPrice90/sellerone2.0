# H A2-T2AC-TW3L Token Selection Ordering Repair

Job ref: `H-A2-T2AC-TW3L-TOKEN-SELECTION-ORDERING-REPAIR`

## Purpose

Repair the H token-selection route so `A2-T2AC-TW3L` does not keep selecting an older fallback token when newer receipt tokens exist for the same SKU.

## Business Reason

The current guard blocks unsafe floor writes, but that still leaves Luke exposed if the SKU sits unresolved. The system must either produce a clean floor from the correct stock token or keep the issue visibly escalated.

## Scope

Code and test repair only.

Allowed:

- inspect H token selection code
- inspect B token ledger schema
- add or update focused tests
- repair token ordering logic if the root cause is confirmed
- add MOT/manager alert logic for `token_selection_conflict` plus missing clean floor
- produce proof using local test data or read-only current outputs

## Required Output

Write:

`CONTROL/H_A2_T2AC_TW3L_TOKEN_SELECTION_ORDERING_REPAIR_RESULT_20260612.md`

The result must show:

- old behavior: fallback token selected first
- new behavior: valid receipt token selected first, or a clearly justified blocked state
- floor remains blocked if proof is not clean
- MOT/manager visibility now treats this as active risk, not parked work
- tests passed

## Forbidden Actions

Do not:

- change Amazon prices
- edit token ledger data
- write Google Sheets
- edit queues
- edit Product DB or local DB facts
- restart runtime
- modify Task Scheduler
- call Amazon
- delete outputs
- force a repricer write

## Definition Of Done

Complete when the focused tests pass and the result file proves the safe behavior.

