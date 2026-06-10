# SellerOne 2.1 Control Inventory

Job: `SO21-CONTROL-INVENTORY`

Generated: 2026-06-08 11:45 UK

## Plain-English Summary

SellerOne has a good control direction, but too many places currently look like the "real" control system.

The best canonical queue candidate is the approved task packet system. The biggest drift risks are old prompt folders, old plan folders, `CODING_PLAN.md` carrying too much live history, `current_state.json` lagging newer MOT evidence, and many paused automations that should not be restarted automatically.

This inventory did not run worker cycles, change business data, restart automations, edit queues, change prices, write Sheets, align databases, or delete outputs.

## Evidence Snapshot

Automation evidence:

- Codex automations found: 19
- Active automations: 0
- Paused automations: 19

Latest MOT evidence:

- file: `out/systems/M/mot/mot_latest.md`
- observed UTC: 2026-06-08T10:16:48Z
- status: `decision_needed`
- fails: 8
- warnings: 19
- decisions: 1

Task packet folders:

| Folder | Files | Classification |
|---|---:|---|
| `sellerone_manager/tasks/approved` | 182 | keep as canonical queue candidate |
| `sellerone_manager/tasks/blocked` | 35 | keep as blocked queue |
| `sellerone_manager/tasks/proposed` | 11 | merge into queue contract |
| `sellerone_manager/tasks/archive` | missing | create |
| `sellerone_manager/tasks/done` | 1 | archive/retire placeholder |
| `sellerone_manager/tasks/in_progress` | 1 | archive/retire placeholder |
| `sellerone_manager/tasks/rejected` | 1 | archive/retire placeholder |

Other control stores:

| Path | Files or lines | Classification |
|---|---:|---|
| `sellerone_manager/CODING_PLAN.md` | 937 lines | merge active state into Control files, then archive historical sections |
| `sellerone_manager/current_state.json` | last changed 2026-06-06 16:49 UK | machine support only |
| `sellerone_manager/CONTROL/CURRENT_STATE.md` | created | keep as human-readable state |
| `sellerone_manager/CONTROL/ARCHITECTURE_DECISIONS.md` | created | keep as Architect decision record |
| `sellerone_manager/agent_launch_prompts` | 8 files | archive or convert useful parts to templates/skills |
| `sellerone_manager/thread_prompts` | 13 files | archive or convert useful parts to templates/skills |
| `sellerone_manager/thread_starters` | 6 files | archive or convert useful parts to templates/skills |
| `sellerone_manager/goals` | 12 files | merge into backlog, then archive |
| `sellerone_manager/project_threads` | 24 files | archive as history/template library |
| `plans/active` | 475 files | legacy plan store, not canonical queue |
| `plans/archive` | 85 files | archive/history |
| `project_control` | 281 files, about 508 MB | keep selected governance files, Custodian review required for backups/storage |
| `out/systems/M` | 264 files | generated manager evidence, not source of truth |
| `docs/manager-briefing` | 6 files | generated communication mirror |
| `config/manager` | 73 files | keep policy/config support |

## Keep

### Approved Task Packets

Path:

- `sellerone_manager/tasks/approved/*.md`
- `sellerone_manager/tasks/blocked/*.md`

Decision:

- Keep as the leading canonical queue candidate.

Reason:

- These packets already carry bounded scope, `job_ref`, proof language, allowed actions, forbidden actions, and Luke decision boundaries.

Required cleanup:

- Add or formalize `tasks/archive`.
- Reconcile status values.
- Define how `proposed`, `approved`, `blocked`, `review`, `proved`, and `archived` map to files and generated indexes.

### Task Packet Engine

Path:

- `sellerone_manager/task_packets.py`
- `sellerone_manager/app.py`
- `out/systems/M/approved_task_packets.csv`

Decision:

- Keep, but clarify source-of-truth boundaries.

Reason:

- `task_packets.py` writes/refreshes packet markdown and the generated CSV index.
- `approved_task_packets.csv` should remain a generated index, not the human-authored source.

Required cleanup:

- Queue contract must state whether markdown or CSV wins if they disagree.
- Status updates must stay explicit and auditable.

### MOT Evidence

Path:

- `out/systems/M/mot/`
- `sellerone_manager/hourly_mot.py`

Decision:

- Keep as independent health evidence.

Reason:

- MOT is the outside inspector. It should reveal failures, not hide them.

Required cleanup:

- MOT worklist rows must become ticket candidates, not a second live queue.
- MOT status should feed `CURRENT_STATE.md`.

### Manager Task Board

Path:

- `sellerone_manager/task_board.py`
- `sellerone_manager/task_board_ui.py`
- `run_Manager_Task_Board_UI.bat`

Decision:

- Keep as read-only view.

Reason:

- It already reads `approved_task_packets.csv` and `mot_worklist.csv`.
- It is useful for Luke, but it must not become the source of truth.

Required cleanup:

- Queue contract must state that the board displays state; it does not own state.

### Manager Briefing

Path:

- `sellerone_manager/manager_briefing.py`
- `sellerone_manager/manager_briefing_ui.py`
- `run_Manager_Briefing_UI.bat`
- `out/systems/M/communications/`
- `docs/manager-briefing/`

Decision:

- Keep as read-only communication layer.

Reason:

- It is the right Luke-facing format.

Required cleanup:

- It currently reads `current_state.json`; it should move toward evidence-generated `CURRENT_STATE.md` or direct MOT/queue evidence.

### Root And Manager Rules

Path:

- `AGENTS.md`
- `sellerone_manager/AGENTS.md`

Decision:

- Keep, but shorten and de-duplicate after the queue contract.

Reason:

- The safety rules are important.
- The current instruction load is too large and overlaps with other manager documents.

Required cleanup:

- Preserve protected-action boundaries.
- Move repeatable workflows into skills or templates.
- Remove outdated current-state assumptions.

## Merge

### Manager Chat Rules

Path:

- `sellerone_manager/MANAGER_CHAT.md`

Decision:

- Merge into the Rep role and then shorten.

Reason:

- It contains good communication rules, but it also carries older manager-thread instructions and setup flow.

Target:

- Rep rules in `AGENTS.md` or a SellerOne manager skill.

### Cycle Sub-Manager Rules

Path:

- `sellerone_manager/CYCLE_SUB_MANAGER_CHAT.md`

Decision:

- Merge useful MOT method into reusable templates; retire visible cycle-sub-manager identity.

Reason:

- SellerOne 2.1 should not have visible cycle sub-managers as a standing operating model.
- Cycle-specific investigation can still happen as a bounded Builder or Reviewer ticket.

### Worker Chat Rules

Path:

- `sellerone_manager/WORKER_CHAT.md`

Decision:

- Keep as a Builder template, but merge repeated safety rules back to the central rules.

Reason:

- Worker boundaries are useful.
- Repeating the same rules across multiple chat files increases drift.

### Coding Plan

Path:

- `sellerone_manager/CODING_PLAN.md`

Decision:

- Merge current live items into `CONTROL/CURRENT_TICKETS.md` and `CONTROL/BACKLOG.md`, then archive historical sections.

Reason:

- At 937 lines, it has become running memory plus old proof history.
- It is useful, but too big to be the daily control desk.

### Project Control Governance

Path:

- `project_control/DUE_CHECK_REGISTER.csv`
- `project_control/TASK_QUEUE.md`
- `project_control/ROADMAP_SYSTEM_MAP.md`
- `project_control/EXPECTATIONS/*.md`

Decision:

- Keep by function, but merge their role into the queue contract.

Reason:

- Due checks, roadmap, and expectations are useful.
- They must not compete with approved task packets as the active engineering queue.

### Active Plans

Path:

- `plans/active`

Decision:

- Merge live commitments into the canonical queue, then treat as historical planning library.

Reason:

- 475 files is too much for a normal front desk.
- Some active plans may still contain valid deferred checks or historical proof.

## Archive

### Prompt And Thread Libraries

Paths:

- `sellerone_manager/agent_launch_prompts`
- `sellerone_manager/thread_prompts`
- `sellerone_manager/thread_starters`
- `sellerone_manager/project_threads`

Decision:

- Archive as history/template library after useful parts are extracted.

Reason:

- These folders represent the old visible multi-manager approach.
- They should not remain live instruction sources.

Do not delete:

- Keep until useful templates are moved into skills or queue templates.

### Old Daily And Hometime Plans

Paths:

- `sellerone_manager/DAILY_MANAGER_PLAN_*.md`
- `sellerone_manager/DAYTIME_MANAGER_PLAN_*.md`
- `sellerone_manager/HOMETIME_PLAN_*.md`
- `sellerone_manager/TONIGHT_MANAGER_PLAN_*.md`
- `sellerone_manager/MORNING_ISSUE_PLAN_*.md`

Decision:

- Archive as history.

Reason:

- They are useful proof of how the manager system evolved, but should not drive current state.

### Old Goal Files

Path:

- `sellerone_manager/goals`

Decision:

- Merge any still-open goal into backlog, then archive.

Reason:

- Goals should not be a parallel task system.

## Retire

### Visible Dispatcher Role

Decision:

- Retire as a visible role.

Reason:

- Dispatching is a queue function. A separate visible Dispatcher increases state drift.

### Cycle-Specific Heartbeat Managers

Examples:

- F cooldown heartbeat
- SellerOne weekend F durability pulse
- O readiness pulse
- O/H maintenance automation

Decision:

- Do not restart by default.

Reason:

- They are too easy to turn into permanent micro-managers.
- Reintroduce only after a stable workflow earns a narrow automation.

### Manager-Per-Cycle Prompt Model

Paths:

- `agent_launch_prompts/01_B_ORDER_TRUTH_MANAGER_PROMPT.md`
- `agent_launch_prompts/02_H_SAFETY_LAYER_MANAGER_PROMPT.md`
- `agent_launch_prompts/03_E_ANALYTICS_PROOF_MANAGER_PROMPT.md`
- `agent_launch_prompts/04_F_PRICE_LIST_MANAGER_PROMPT.md`
- `agent_launch_prompts/05_O_MID_BUILD_MANAGER_PROMPT.md`
- similar files in `thread_prompts`

Decision:

- Retire as a live model.

Reason:

- The useful pattern is bounded work by ticket, not standing manager personalities per cycle.

## Gaps Found

### Gap 1 - No `tasks/archive`

Problem:

- The task system has approved, blocked, proposed, and placeholder done/in_progress/rejected folders, but no real archive folder.

Risk:

- Completed work stays mixed with active work or lives in old plan files.

Recommended next:

- Create `tasks/archive` during `SO21-QUEUE-CONTRACT`.

### Gap 2 - `current_state.json` Is Stale Against MOT

Problem:

- `current_state.json` last changed on 2026-06-06 16:49 UK.
- MOT output is newer, with latest observed UTC 2026-06-08T10:16:48Z.

Risk:

- Manager briefing can accidentally trust older state over newer evidence.

Recommended next:

- Create a `CURRENT_STATE.md` generator or manual update protocol.
- Update manager briefing to use the new state rule later.

### Gap 3 - `CODING_PLAN.md` Is Overloaded

Problem:

- It is 937 lines and carries old F proof history plus current 2.1 state.

Risk:

- Future agents may treat old monitoring notes as current instructions.

Recommended next:

- Move active work to `CURRENT_TICKETS.md`.
- Move backlog to `BACKLOG.md`.
- Archive older phase history.

### Gap 4 - Prompt Folders Still Look Live

Problem:

- There are 8 agent launch prompts, 13 thread prompts, 6 thread starters, and 24 project-thread files.

Risk:

- A future session can accidentally revive the old multi-manager structure.

Recommended next:

- Mark these folders as template/history in instruction cleanup.
- Move reusable parts into skills or ticket templates.

### Gap 5 - Project Control Is Large

Problem:

- `project_control` has 281 files and about 508 MB.
- Large backup and cleanup artifacts dominate the size.

Risk:

- Storage growth will keep returning without a Custodian policy.

Recommended next:

- Run `SO21-STORAGE-CUSTODIAN` as preview-only.
- Do not delete until retention classes and quarantine rules are approved.

### Gap 6 - Automations Are Paused But Not Rebuilt

Problem:

- All 19 automations are paused, but the future automation set is not yet defined.

Risk:

- Restarting old automations would revive old control roles.

Recommended next:

- Keep paused until `SO21-AUTOMATION-REBUILD`.

## Immediate SellerOne 2.1 Task Order

1. `SO21-QUEUE-CONTRACT`
   - choose canonical queue rules
   - define status values
   - define source-of-truth priority
   - create `tasks/archive`

2. `SO21-CURRENT-STATE-GENERATOR`
   - define how `CURRENT_STATE.md` is generated from MOT, task packets, automation state, and policy files
   - stop relying on stale `current_state.json` for Luke-facing state

3. `SO21-CUSTODIAN-POLICY`
   - create retention classes
   - classify storage folders
   - preview cleanup only

4. `SO21-INSTRUCTION-CLEANUP`
   - shorten root and manager instructions
   - mark old prompt folders as history/templates
   - move repeated workflows into skills/templates

5. `SO21-AUTOMATION-REBUILD`
   - rebuild only small stable automations after the queue contract exists

## No-Touch List During Inventory

Do not:

- run A, B, E, H, F, or O worker cycles
- restart FPM/F061 or other worker owners
- change prices
- edit queues
- write Google Sheets
- align Product DB or local DB facts
- delete outputs
- start purchase-order, receiving, or send-to-Amazon work
- bypass Amazon security
- restart old automations

## Inventory Result

`SO21-CONTROL-INVENTORY` is complete as a first pass.

The next architecture task is not code. It is the queue contract.
