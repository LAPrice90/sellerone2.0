# SellerOne Manager

This is the folder to open in Codex when you want to talk to the manager instead of digging through the main system.

The manager is for maintenance automation, repair control, and extension planning.

It is not the business data UI. If something is running normally, the manager should keep it quiet unless Luke needs to make a decision.

## First Chat Prompt

When you open this folder in Codex, type:

```text
Read MANAGER_CHAT.md and act as SellerOne Manager.
```

After that, you can speak normally.

## If You Open A Worker Chat Elsewhere

You should not have to explain the manager idea again.

Worker chats should read:

```text
sellerone_manager/WORKER_CHAT.md
```

The rule is:

```text
Manager chooses and explains.
Worker claims the approved task packet and repairs inside the boundary.
Luke only gets pulled in for protected decisions.
```

If a worker chat starts acting like a normal coding chat, tell it:

```text
Read sellerone_manager/WORKER_CHAT.md and work only from the approved manager packet.
```

## Optional Command

Run this from this folder:

```powershell
.\what_next.ps1
```

It answers:

- is the system OK, warned, or blocked
- whether Luke needs to act
- whether Codex has a task
- the next safe batch
- what must not be touched
- where the proof files are

The front door refreshes the read-only manager control outputs when manager manifests are available. It does not run workers.

## Current State File

The canonical manager state is:

```text
current_state.json
```

Codex should read this before proposing work.

## Manager Charter

The operating charter is:

```text
MANAGER_CHARTER.md
```

Codex should read it before planning or widening the manager's authority.

## Multi-Flow Manager Outputs

The all-flow maintenance control files are:

```text
out/systems/M/flow_maintenance_state.csv
out/systems/M/flow_expectation_reconciliation.csv
out/systems/M/manager_task_candidates.csv
out/systems/M/latest_manager_control_report.md
```

The rollout order is:

```text
A -> B -> E -> H -> F -> O
```

## No-Token Hourly MOT

The first independent reviewer is for A:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow A
```

It does not run workers, call Amazon, or use AI tokens. It only checks the proof files A should already have written.

It writes:

```text
out/systems/M/mot/mot_latest.csv
out/systems/M/mot/mot_latest.json
out/systems/M/mot/mot_latest.md
out/systems/M/mot/mot_history.jsonl
out/systems/M/mot/mot_worklist.csv
out/systems/M/mot/mot_retest_queue.csv
```

Legacy compatibility copies are also written at:

```text
out/systems/M/hourly_mot_A.csv
out/systems/M/hourly_mot_A.json
out/systems/M/hourly_mot_latest.md
```

To install the hourly Windows task, run:

```powershell
.\install_manager_hourly_mot_task.ps1
```

The Windows task name is:

```text
SellerOne Manager Hourly MOT
```

Do not delete the older system-wide morning MOT yet. It still acts as a safety net for restart, ownership, due-check, and post-A checks until the manager MOT has copied or replaced that coverage.

For MOT-owned repairs, Codex should not mark work complete after a code edit. The row should move to `fixed_needs_retest`, then the MOT should rerun, and only real proof should move it to `proved`.

## Cycle Sub-Managers

Each cycle sub-manager should extend the independent MOT for its own cycle.

Do not let a cycle chat treat the old health FAIL/WARN count as final proof. The old checks are only clues.

The real setup order for each cycle is:

```text
1. Define what the cycle should produce.
2. Add read-only MOT checks for proof files, row counts, SQL tables, locks, heartbeats, and handoff markers.
3. Map manager expectations to those MOT checks.
4. Create bounded worker task packets only when the MOT finds a repairable problem.
5. Ask Luke only for protected actions.
```

For B, the next manager-owned setup job is to add B to the independent MOT script. It should not be treated as proven just because the old B checklist has no active alert.

## Approved Task Packets

Before worker repair, refresh approved packets:

```powershell
python -m sellerone_manager.app --refresh-approved-tasks
```

Then claim the next safe packet:

```powershell
python -m sellerone_manager.app --claim-approved-task
```

Safe non-Luke code repairs inside a claimed packet are standing-approved. Protected actions still need Luke.

## Goal And Task Files

Luke's ideas should become goal files first, then bounded Codex task files.

Goal folders:

```text
goals/inbox/
goals/active/
goals/blocked/
goals/done/
```

Task folders:

```text
tasks/proposed/
tasks/approved/
tasks/in_progress/
tasks/done/
tasks/rejected/
```

## What This Folder Is

This folder is the manager control desk.

It is not the worker system.
It should not run scans, restart workers, edit queues, write legacy Sheets, or change prices.

## What To Ask Codex Here

Good prompts:

- What is blocking F right now?
- Does Luke need to make a decision?
- What is the next safe Codex batch?
- Show me the current maintenance state in plain English.
- Continue with the next manager-owned batch.

Bad prompts for this folder:

- Run the scanner.
- Restart F061.
- Change queue state.
- Write to legacy Sheets.
- Fix worker logic without a manager task.
