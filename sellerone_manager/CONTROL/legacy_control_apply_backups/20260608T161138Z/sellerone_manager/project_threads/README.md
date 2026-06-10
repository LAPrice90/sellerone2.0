# SellerOne Project Thread Control

This folder is the canonical launch pack for visible Codex project threads.

Use these files when creating a new visible thread inside the SellerOne project. Do not use the older duplicate prompt folders unless you are checking historical context:

- `sellerone_manager/thread_prompts/`
- `sellerone_manager/agent_launch_prompts/`
- `sellerone_manager/thread_starters/`

## Plain-English Model

The project should run like a business with departments:

- Main Manager Thread: the front desk and single truth board.
- Cycle Worker Threads: one visible thread per cycle job.
- MOT: the independent inspector that checks proof files from outside the cycles.
- Approved Task Packets: the work orders workers must start from.

The manager does not use random chats as memory. The durable memory is:

- `sellerone_manager/current_state.json`
- `out/systems/M/mot/mot_rollup_latest.md`
- `out/systems/M/mot/mot_worklist.csv`
- `out/systems/M/approved_task_packets.csv`
- `out/systems/M/flow_maintenance_state.csv`
- this `sellerone_manager/project_threads/` folder

The standard visual job view is:

```text
run_Manager_Task_Board_UI.bat
sellerone_manager/task_board_ui.py
```

It reads the manager task packet and MOT worklist files. It is read-only in V1, so it must not move cards, change task status, run worker cycles, or approve protected work.

## Launch Order

Start with one visible project thread at a time unless the work is truly independent.

1. B worker thread - current active blocker.
2. H safety thread - high-risk repricing safety only.
3. F proof thread - scanner/source proof cleanup.
4. O build thread - mid-build readiness and walkthrough proof.
5. E proof thread - analytics confidence warnings.
6. Main manager combiner - fold worker results into the single board.
7. Manager task board UI thread - maintain the read-only visual coding-jobs board when the board itself needs changes.

A is watch-only unless A MOT fails.

## How To Use A Thread Prompt

1. In Codex, create a new thread inside the SellerOne project.
2. Paste the full prompt from the relevant file in this folder.
3. Let that thread work only on its assigned job.
4. When it finishes, paste the result back into the Main Manager Thread.
5. Run `06_MAIN_MANAGER_COMBINER_THREAD.md` after worker results return.

## Non-Negotiable Boundaries

Every project thread must stop before:

- price changes
- queue edits
- Google Sheet writes
- publishing
- local DB alignment or rewriting facts
- output deletion
- live worker cycle runs without an approved proof window
- scheduler ownership changes without a restoration proof packet
- business judgement on uncertain rows

## Thread Result Shape

Every worker thread must finish with:

```text
Decision needed: yes - <only include this line when there is a real Luke decision>
What this cycle now proves
What changed
What remains blocked or parked
Proof run and result
Files changed
Recommended next move
```
