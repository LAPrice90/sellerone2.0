# SellerOne 2.1 Instruction Cleanup Plan

Job: `SO21-INSTRUCTION-CLEANUP`

Created: 2026-06-08

## Plain-English Status

SellerOne now has a cleaner instruction model.

The old state was seven overlapping clipboards: root rules, manager rules, role files, active coding plans, prompt folders, MOT notes, and chat history. The new state is one front door with role routing.

## What Changed

- Root `AGENTS.md` is now a short SellerOne 2.1 bootstrap.
- Manager `AGENTS.md` is now a short Manager workspace bootstrap.
- `CONTROL/ROLE_BOOTSTRAP.md` defines which role reads which rules.
- `CONTROL/RUNTIME_SAFETY_RULES.md` holds detailed runtime safety rules.
- `CONTROL/CURRENT_TICKETS.md` and `CONTROL/BACKLOG.md` are now the readable work lists.
- `CONTROL/CURRENT_STATE.md` remains the human-readable state anchor.
- Legacy pre-cleanup AGENTS files were backed up under `CONTROL/instruction_cleanup_backups/20260608T1155_instruction_cleanup/`.

## Instruction Source Of Truth

| Source | 2.1 Role | Status |
|---|---|---|
| Root `AGENTS.md` | repo-wide bootstrap | shortened |
| `sellerone_manager/AGENTS.md` | manager workspace bootstrap | shortened |
| `CONTROL/ROLE_BOOTSTRAP.md` | role router | created |
| `CONTROL/RUNTIME_SAFETY_RULES.md` | runtime safety detail | created |
| `MANAGER_CHAT.md` | manager role protocol | keep for role detail |
| `WORKER_CHAT.md` | worker role protocol | keep for role detail |
| `CYCLE_SUB_MANAGER_CHAT.md` | cycle manager protocol | keep for role detail |
| `CONTROL/CURRENT_STATE.md` | human state | generated |
| `CONTROL/CURRENT_TICKETS.md` | active work | generated |
| `CONTROL/BACKLOG.md` | parked/future work | generated |
| `CODING_PLAN.md` | legacy active implementation memory | context only until archived |
| `WORK_LOG.md` | historical context | not canonical |
| old prompt folders | templates/history | not canonical |

## What Was Not Changed

- No worker code was changed.
- No worker cycle was run.
- No task packet was moved.
- No queue state was edited.
- No output was deleted.
- No automation was restarted.

## Remaining Cleanup

Recommended next instruction tasks:

- `SO21-CODING-PLAN-ARCHIVE`: move the old F login `CODING_PLAN.md` into historical context and replace it with a small current manager plan.
- `SO21-ROLE-FILE-TRIM`: shorten `MANAGER_CHAT.md`, `WORKER_CHAT.md`, and `CYCLE_SUB_MANAGER_CHAT.md` now that role routing exists.
- `SO21-SKILL-SPECS`: turn repeat workflows into skill or template specs, starting with manager briefing, worker packet repair, MOT review, and Custodian dry-run.
- `SO21-PROMPT-FOLDER-ARCHIVE`: mark old prompt folders as template/history only.

## Acceptance Checks

This task is complete when:

- the two live AGENTS files route into the 2.1 control model
- detailed safety rules still exist in a durable file
- current state recommends the next control task
- focused manager tests pass
- no business runtime changes occurred

## Current Result

Status: initial instruction cleanup complete.

Next recommended control task: `SO21-AI-USAGE-REPORT`.
