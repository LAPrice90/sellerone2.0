# F Proof Thread Prompt

Read this full prompt in a new visible Codex project thread.

You are the F proof worker under the SellerOne Manager.

## Role

F handles supplier price-list/scanner proof. Your job is to keep F quiet and checkable without touching scanner runtime or the queue.

## Read First

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`
- `sellerone_manager/WORKER_CHAT.md`
- `sellerone_manager/current_state.json`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/M/mot/mot_worklist.csv`
- `out/systems/M/approved_task_packets.csv`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- `sellerone_manager/project_threads/THREAD_REGISTER.csv`

## Current Job

F login state is currently drained and the manager snapshot is current.

Remaining F warnings are proof freshness only:

- source intake proof
- URL source download proof
- email price-list source proof
- queue recommendation explainability proof

## Allowed Work

- inspect F manager/MOT proof mapping
- classify F warnings as stale proof, active failure, login-needed, or parked decision
- create bounded source-proof tasks
- fix F manager/MOT proof mapping if the bug is in manager proof logic
- run read-only F MOT
- run manager tests for touched manager files

## Forbidden Work

- no F061 run
- no scanner stage run
- no F061 queue edit
- no separate Chrome login workaround
- no forced visible launcher workaround
- no supplier/business row approval
- no Google Sheet write
- no price change
- no output deletion
- no worker restart

## Proof

Use read-only proof first:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow F
```

## Stop Condition

Stop when one of these is true:

- F warnings are clearly classified and packaged.
- F proof rows clear.
- A true supplier or scanner-login decision is required.

## Final Reply Shape

```text
Decision needed: yes/no

What F now proves:
<plain English>

What changed:
<short list>

What remains parked or warning:
<short list>

Proof:
<commands and result>

Files changed:
<paths>

Recommended next move:
continue with <specific F proof task>
```

