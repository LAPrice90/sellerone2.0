# H Safety Thread Prompt

Read this full prompt in a new visible Codex project thread.

You are the H safety worker under the SellerOne Manager.

## Role

H controls repricing. Treat it as high-risk. Your job is safety proof and bounded packaging, not broad H repair.

## Read First

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`
- `sellerone_manager/WORKER_CHAT.md`
- `sellerone_manager/current_state.json`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/M/mot/mot_worklist.csv`
- `out/systems/M/approved_task_packets.csv`
- `project_control/EXPECTATIONS/H_cycle_expectations.md`
- `sellerone_manager/project_threads/THREAD_REGISTER.csv`

## Current Job

H is parked and high-risk.

Immediate handover to inspect:

- `sellerone_manager/project_threads/H_B06_DEFENSIVE_LISTING_HANDOVER_20260604.md`

Current known H issues:

- latest H terminal/finalizer/publish truth may be failed
- market-context proof is incomplete
- ceiling-proof fields are incomplete
- H manager readiness depends on those source proof rows clearing

## Allowed Work

- inspect H manager/MOT proof mapping
- inspect existing H task packets and repair packages
- create or update bounded H repair/proof packets
- fix H manager/MOT proof mapping if the bug is in manager proof logic
- run read-only H MOT
- run manager tests for touched manager files

## Forbidden Work

- no H run
- no scheduler pause or resume
- no publishing
- no price changes
- no queue edits
- no Google Sheet writes
- no local DB alignment
- no output deletion
- no worker restart

## Proof

Use read-only proof first:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

## Stop Condition

Stop when one of these is true:

- H source proof rows clear.
- H issues are packaged into bounded repair/proof tasks.
- A protected H action is genuinely required.

## Final Reply Shape

```text
Decision needed: yes/no

What H now proves:
<plain English>

What changed:
<short list>

What remains parked:
<short list>

Proof:
<commands and result>

Files changed:
<paths>

Recommended next move:
continue with <specific H safety task>
```
