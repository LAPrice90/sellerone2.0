# CODEX.md

## Purpose

This file is the short session handoff for Codex in VS Code.

Primary behavior authority remains `AGENTS.md`.
This file exists to point Codex to the current planning system and reduce drift between sessions.

## Read Order At Session Start

1. `AGENTS.md`
2. `CODEX.md`
3. `project_control/OPERATING_SYSTEM.md`
4. active plan files in `plans/active/<plan_slug>/`

## Working Rules

- Treat `AGENTS.md` as the main behavior contract.
- Treat the active plan folder as the durable memory for the current ticket.
- Do not treat chat history as the only source of truth.
- Before coding, summarise:
  - plan goal
  - current phase in `CODING_PLAN.md`
  - current batch scope
  - files allowed to change
  - tests required
  - proof required
- Keep execution tied to the current batch.
- Keep multi-phase execution tied to `CODING_PLAN.md`, not chat memory.
- When live proof is required, use a bounded monitored validation window with explicit poll cadence and timeout.
- Before defaulting to stale-artifact waiting, check whether a forced proof window exists and write it into `CODING_PLAN.md`.
- Use `scripts/one_off/P002_plan_forced_proof_window.py` for A, B, E, or H flow-owned proof windows.
- Treat next scheduled cycle waiting as fallback only after the exact blocker to forced proof is recorded.
- Treat monitored validation as passive by default. Do not interrupt the user for routine checkpoints.
- Treat known unchanged alerts as morning-MOT digest material, not something to repeat in every unrelated reply.
- When the user asks for morning MOT fix execution, fix clear blockers quietly and interrupt only for real decisions or milestone summaries.
- Write factual completion evidence into the batch reply file.

## Plan Folder Standard

Every active plan should contain:
- `PROJECT_BRIEF.md`
- `INCIDENT_BRIEF.md`
- `PLAN.md`
- `CODING_PLAN.md` for multi-phase or runtime-owned work
- `PLAN_STATUS.md`
- `EXECUTION_BATCH_###.md`
- `DEBUG_BATCH_###.md`
- `EXECUTION_BATCH_###_REPLY.md`
- `DATA_CONTRACTS.md`
- `RUNBOOK.md`

## Lane Selection

Use the request type to choose the starting lane.

### Build lane

Use when the request is about:
- a new feature
- a new extension
- a new output
- a new workflow step

Start with:
- `PROJECT_BRIEF.md`
- `PLAN.md`
- `CODING_PLAN.md` if the work will span phases
- `EXECUTION_BATCH_001.md`

### Debug lane

Use when the request is about:
- an error
- stale data
- a missing update
- a wrong join
- a broken integration
- an unexpected behavior change

Start with:
- `INCIDENT_BRIEF.md`
- `CODING_PLAN.md` if the fix will span phases or require live proof
- contract and owner review
- `DEBUG_BATCH_001.md`

Core debug rule:
- treat the fault as a contract violation first
- find the owner
- compare expected state vs actual state
- fix root cause before consumer-level patching

## If No Plan Folder Exists Yet

- Use `scripts/one_off/P001_create_plan_workspace.py` to scaffold one.
- Then choose the lane:
  - build lane -> fill the brief, plan, and coding plan before implementation starts
  - debug lane -> fill the incident brief, coding plan, and debug batch before code changes start

## Drift Prevention

- One owner per output dataset.
- Freshness expectations must be written down.
- New outputs must have schema checks.
- New behavior must have proof.
- Root-cause fixes come before downstream patching.

## Model And Settings Rule

- Do not hardcode long-term model choices into planning docs or business scripts unless a specific script truly requires it.
- Prefer repo config and environment/config files for settings.
- Use the best approved model available at the time of execution.

## Role And Mode Guide

- Planning / architecture thinking:
  - use GPT with high reasoning
- Research unknowns:
  - use Deep Research when outside facts are needed
- Execution:
  - use Codex with medium to high reasoning
- Batch execution:
  - use Codex with high reasoning and strict scope control
- Review / validation:
  - use GPT with high reasoning
- Small fixes:
  - use Codex with medium reasoning

Keep the roles separate:
- Architect = GPT
- Builder = Codex
- Inspector = GPT
