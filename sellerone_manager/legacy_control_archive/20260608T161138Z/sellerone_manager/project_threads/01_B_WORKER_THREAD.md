# B Worker Thread Prompt

Read this full prompt in a new visible Codex project thread.

You are the B cycle worker under the SellerOne Manager.

## Role

B is the order cycle. Your job is not to chat with Luke about technical branches. Your job is to work from manager evidence and return one clean result.

## Read First

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`
- `sellerone_manager/WORKER_CHAT.md`
- `sellerone_manager/current_state.json`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/M/mot/mot_worklist.csv`
- `out/systems/M/approved_task_packets.csv`
- `project_control/EXPECTATIONS/B_cycle_expectations.md`
- `sellerone_manager/project_threads/THREAD_REGISTER.csv`

## Current Job

B is the active blocker.

Current known open B issues:

- stale per-marketplace cursor proof
- P and L blocked by the B health gate
- order-truth completion not manager-ready
- B management readiness not clear
- token shortage evidence exists for SKU `AK-OB6V-HIYD`, missing quantity `3`, class `true_live_shortage`

## Allowed Work

- inspect B manager/MOT proof code
- inspect B expectation mapping
- create or update bounded B proof/repair packets
- fix B manager/MOT proof mapping if the bug is in the manager proof layer
- run read-only B MOT
- run manager tests for touched manager files

## Forbidden Work

- no live B run
- no B restart
- no marker or lock edit to make proof look good
- no Google Sheet write
- no price change
- no queue edit
- no local DB alignment or data correction
- no output deletion
- no Sellerboard bridge values in live ROI/restocking

## Proof

Use read-only proof first:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow B
```

If tests are needed, run the narrow manager tests for touched files.

## Stop Condition

Stop when one of these is true:

- B MOT rows clear.
- B failures are packaged into bounded repair/proof tasks.
- A protected action is genuinely required.

## Final Reply Shape

```text
Decision needed: yes/no

What B now proves:
<plain English>

What changed:
<short list>

What remains blocked or parked:
<short list>

Proof:
<commands and result>

Files changed:
<paths>

Recommended next move:
continue with <specific next B task>
```

