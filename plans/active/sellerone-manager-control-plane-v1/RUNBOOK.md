# SellerOne Manager Control Plane V1 - Runbook

## Run
From `C:\Users\Luke\Desktop\SellerOne 2.0`:

```powershell
python -m sellerone_manager.app --flow F_price_list_manager --read-only --write-report
```

For the all-flow manager control desk:

```powershell
python -m sellerone_manager.app --flow all --read-only --write-report
```

## Luke Front Door
Use this command when you want the manager to answer what matters now:

```powershell
python -m sellerone_manager.app --what-next
```

This prints one short operating view:
- system status
- active flow
- current state
- whether Luke needs to act
- whether Codex has a task
- one next safe batch
- boundaries that must not be touched
- latest manager evidence paths

It also writes the canonical operating state to:

```text
sellerone_manager/current_state.json
```

When manager module manifests are available, this front-door command refreshes read-only manager control outputs before writing `current_state.json`. It does not run workers, restart anything, write legacy Sheets, edit queues, change pricing, or dispatch jobs.

## Codex App Chat Workflow
Luke can use the manager without operating PowerShell.

1. Open this folder in Codex:

```text
C:\Users\Luke\Desktop\SellerOne 2.0\sellerone_manager
```

2. Type this:

```text
Read MANAGER_CHAT.md and act as SellerOne Manager.
```

3. Then speak normally, for example:

```text
I want the supplier scanner to be easier to monitor.
```

The manager should then:
- read `current_state.json`
- read the latest manager reports
- convert the idea into a goal file
- create proposed Codex task files if useful
- explain the next approved batch or stop
- avoid giving Luke technical repair work unless a true human decision is needed

## Goal And Task Workflow
Goal files live under:

```text
sellerone_manager/goals/
```

Task files live under:

```text
sellerone_manager/tasks/
```

Goals describe what Luke wants in plain English.

Tasks describe bounded Codex work with allowed files, forbidden files, acceptance checks, and a stop condition.

Folders:
- `goals/inbox/` for raw ideas not accepted yet
- `goals/active/` for accepted goals
- `goals/blocked/` for goals waiting on a decision or missing evidence
- `goals/done/` for completed goals
- `tasks/proposed/` for suggested Codex work
- `tasks/approved/` for Codex work approved to start
- `tasks/in_progress/` for active Codex work
- `tasks/done/` for completed Codex work
- `tasks/rejected/` for work the manager decided not to do

## Read The Result
- Plain-English report: `out/systems/M/latest_f_price_list_manager_report.md`
- Current operating state JSON: `sellerone_manager/current_state.json`
- Snapshot CSV: `out/systems/M/f_price_list_manager_snapshot.csv`
- Health CSV: `out/systems/M/manager_health.csv`
- Incident CSV: `out/systems/M/manager_incidents.csv`
- Codex repair queue: `out/systems/M/codex_repair_queue.csv`
- Codex repair event history: `out/systems/M/codex_repair_events.csv`
- Self-organisation report: `out/systems/M/self_organisation_gaps.csv`
- F script registration CSV: `out/systems/M/self_organisation/latest_f_script_registration_report.csv`
- F script registration JSON: `out/systems/M/self_organisation/latest_f_script_registration_report.json`
- F self-organisation markdown: `out/systems/M/self_organisation/latest_f_self_organisation_report.md`
- F manifest priority ranking CSV: `out/systems/M/self_organisation/latest_f_manifest_priority_ranking.csv`
- F manifest priority ranking JSON: `out/systems/M/self_organisation/latest_f_manifest_priority_ranking.json`
- F manifest priority markdown: `out/systems/M/self_organisation/latest_f_manifest_priority_report.md`
- Multi-flow maintenance state: `out/systems/M/flow_maintenance_state.csv`
- Expectation reconciliation: `out/systems/M/flow_expectation_reconciliation.csv`
- Manager task candidates: `out/systems/M/manager_task_candidates.csv`
- Manager control report: `out/systems/M/latest_manager_control_report.md`

## Mark Codex Task Progress
Codex can move a manager-owned task through its lifecycle without editing CSV files by hand:

```powershell
python -m sellerone_manager.app --task-status F_storage_drift_preflight_4ddda80247 --status in_progress --note "Started investigation"
```

This only updates manager-owned outputs under `out/systems/M/`. It does not run workers or change the F queue.

## How Luke Should Use The Manager
- Run `python -m sellerone_manager.app --what-next`.
- Read `LUKE ACTION REQUIRED`.
- If it says `no`, Luke does not need to choose from technical files.
- If it says `yes`, do only the exact action shown.
- Use the `LATEST EVIDENCE` paths only if you want to inspect the proof behind the answer.

## How Codex Batches Should Be Driven
- Codex should use `sellerone_manager/current_state.json` and the `NEXT SAFE BATCH` line as the control point.
- Codex should start only the single recommended batch unless Luke explicitly approves a different scope.
- Codex should keep technical repair or manifest work separate from Luke action.
- Codex must not treat `--what-next` as permission to run workers or dispatch jobs.

## Manager vs Worker Responsibilities
- Manager responsibility: read manager-owned outputs, summarize state, rank manager registration work, track Codex tasks, and explain what needs Luke.
- Worker responsibility: run business scripts, write F evidence, write scanner outputs, and own live runtime behavior.
- V1 boundary: the manager can report and organize. It cannot run, restart, repair, dispatch, edit queues, write sheets, change pricing, or delete outputs.
- V1.1 authority target: task-control first. The manager can create repair or extension task candidates with proof requirements, but it cannot dispatch worker jobs.

## Good Result
- Command exits with code `0`.
- Console shows `manager_execution_errors=0`.
- Report explains the earliest blocker first.
- If CLF is recommended but F is blocked by storage drift, the report says storage drift blocks the scanner before CLF can start.
- Repeated runs update the same Codex repair task instead of creating a fresh duplicate task.
- Task status changes are recorded in `out/systems/M/codex_repair_events.csv`.
- Self-organisation gaps do not block F operation. They create Codex review recommendations only.
- Manifest priority ranking chooses the next F scripts for Codex to register. It does not create those manifests in the same run.
- Registered script count includes every F manifest in `config/manager/modules/`, not just the top-level F manager manifest.

## Current Script-Level F Manifests
- `config/manager/modules/FPM170_supervise_live_cycle.json`
- `config/manager/modules/FPM129_storage_drift_guard.json`
- `config/manager/modules/FPM050_build_next_action_report.json`

## Safety
This command is read-only toward workers. It only writes manager-owned outputs under `out/systems/M/`.

Do not use this v1 manager to run, restart, pause, resume, or edit worker queues.
