# Manager Task Board UI Thread

Act as a worker agent under the SellerOne Manager.

Your job is to build the read-only Manager Task Board UI. This is a coding-jobs board for Luke to see what Codex and worker chats are working on. It is not the business UI, not the O restocking UI, and not a worker runner.

## Read First

Read these before changing code:

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/MANAGER_PROGRESS_TRACKER.md`
- `out/systems/M/approved_task_packets.csv`
- `out/systems/M/mot/mot_worklist.csv`
- task packet Markdown files under `sellerone_manager/tasks/approved/`
- task packet Markdown files under `sellerone_manager/tasks/blocked/`

## Goal

Build a separate read-only Kanban-style task board for manager-approved coding jobs.

The board should show:

- not started
- in progress
- waiting proof
- proof failed
- blocked
- parked

It should hide proved jobs by default.

Every job must also show a stable human `job_ref` such as `F-EMAIL-SOURCE`. The board should make that the first visible label on the card, keep the full `task_id` inside opened details, and preserve any existing `job_ref` across refreshes.

## Required Behaviour

- Read manager task files only.
- Do not create a new source of truth.
- Do not change task status from the UI.
- Preserve and display `job_ref` for every visible card.
- Search must include `job_ref`, title, full `task_id`, flow, and notes.
- A top Needs Luke strip should list blocked jobs by `job_ref`.
- Do not run A, B, E, H, F, or O worker cycles.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not publish.
- Do not align local DB facts.
- Do not delete outputs.
- Do not restart workers.
- Do not make business decisions.

## UI Expectations

- Keep it separate from the O/operator UI.
- Use cycle badges: A, B, E, H, F, O, M.
- Use cycle colours:
  - A green
  - B blue
  - E purple
  - H red
  - F teal
  - O amber
  - M charcoal
- Each card should show title, cycle, status, priority, protected/Luke gate flag, short note, and proof/retest requirement.
- Each card should show `job_ref` before the title.
- Details can expand, but raw file paths and packet detail should stay hidden until opened.
- Filters should include cycle, status, protected-only, and active-only.

## Proof

Run focused tests for the task board reader and UI helpers.

Then run the standalone UI:

```powershell
python -m streamlit run sellerone_manager/task_board_ui.py
```

Proof must show:

- all lanes render
- F source-proof cards appear
- B protected original-token decision cards appear
- proved O history does not flood the default board
- every visible card has a `job_ref`
- search by `job_ref` finds the matching card
- the Needs Luke strip names blocked jobs by `job_ref`
- the UI does not call task-status update commands

## Reporting Back

Reply in this shape:

```text
Decision needed: yes/no
What the task board now proves
What changed
What remains blocked or parked
Proof run and result
Files changed
Recommended next move
```
