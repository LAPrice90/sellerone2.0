# SO21 Operations Maintenance Policy Acknowledgement

Updated: 2026-06-09 14:12 UK
Role: Operations

## Policy Confirmed

Operations verified the 2026-06-09 Luke clarification in:

- `CONTROL/SO21_BUSINESS_RUNTIME_MAINTENANCE_AUTHORITY.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md` as ADR-0023

## Plain-English Rule

When Luke approves a named task for a named cycle, Operations may use controlled pause, reload, or restart for that same cycle if it is genuinely needed to complete the approved repair, proof, or addition.

This is not a blank kill switch.

## Required Boundaries

- target cycle must be named
- reason must be tied to the approved task
- use the softest safe method
- do not create a second owner
- do not leave the cycle stopped silently
- restart or relaunch proof is mandatory
- post-restart health proof is mandatory
- if restart fails, record the blocker and alert Rep

## Active F Application

For `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`, Operations must not ask Luke again for the same controlled F owner reload/relaunch permission because it is:

- named to the F price-list scanner owner
- tied to the approved F live login proof task
- recorded in `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md`
- bounded to the existing scanner-owned F path and single login controller

The active F Worker thread is already proceeding under that rule.

## Operations Boundary

Operations did not perform runtime pause/restart, process kill, Task Scheduler change, Amazon/security action, browser/profile/cookie mutation, output deletion, price change, Sheet write, database action, purchase, receiving, or send-to-Amazon action in this acknowledgement.
