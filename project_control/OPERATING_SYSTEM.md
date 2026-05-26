# Operating System

## Purpose

This file defines the repo governance workflow, task types, and authority hierarchy for project control. It does not replace `AGENTS.md` for Codex behavior rules, and it does not replace `WORK_LOG.md` for append-only approved history.

## System Workflow

idea -> inspection -> planning -> implementation -> validation

## Workflow Stages

### Idea

- A user request, operational problem, or governance gap is identified.
- The objective and scope are bounded before any implementation work begins.

### Inspection

- Relevant code, control files, logs, and existing artifacts are inspected first.
- Existing authority sources are checked before new content or changes are proposed.
- Routine estate-wide alert review belongs in the morning MOT workflow unless the current ticket is directly about health or the alert materially changed.

### Planning

- Findings are translated into a scoped task, report, or enforcement plan.
- Safe changes are separated from decision-required changes.
- Control-file updates are decided before implementation where governance or architecture is affected.

### Implementation

- Approved changes are made in the narrowest safe scope.
- Existing authority and path rules are followed rather than bypassed with ad hoc fixes.

### Validation

- The changed scope is checked with the narrowest relevant validation available.
- When a safe forced proof window exists, use that owned boundary instead of waiting for the next scheduled cycle.
- Do not read runtime health in the middle of a loop when the loop has not yet reached its own finalization point.
- Outputs, reports, or scope checks are confirmed before work is treated as complete.

## Task Types

### Inspection

- Purpose: gather evidence, map behavior, or classify current state.
- Typical outputs: audits, lineage maps, source classification, current-state snapshots.

### Planning

- Purpose: convert inspected evidence into an ordered execution approach.
- Typical outputs: phased plans, decision lists, authority models, queued work.

### Implementation

- Purpose: make approved repo changes within defined scope.
- Typical outputs: code changes, control-file updates, safe rewires, targeted fixes.

### Validation

- Purpose: confirm the changed scope behaves as expected and that authority or file scope was preserved.
- Typical outputs: compilation checks, narrow script runs when explicitly allowed, file-existence checks, diff or status verification.

## Governance Authority Hierarchy

### 1. `AGENTS.md`

- Role: Codex behavior rules.
- Authority: highest authority for how Codex must behave in this repo.

### 2. `project_control/*`

- Role: project governance, architecture, state summaries, decisions, task queue, workflow, and guardrails.
- Authority: primary project-control lane for what the system is, how it should be governed, and how planned work should be framed.

### 3. `WORK_LOG.md`

- Role: append-only operational history and approved audit trail.
- Authority: canonical historical ledger of approved work and operational state changes.

### 4. Legacy planning files

- Role: reference-only legacy planning and background material.
- Authority: not authoritative project state and not active governance unless a later approved migration promotes specific content upward.

## Role Definitions

### Product Owner

- Defines the business objective, approves scope, and makes unresolved product or ownership decisions.

### Planning Controller

- Maintains the project-control lane by translating repo evidence into current architecture, decisions, state, guardrails, and queued work.

### Codex Executor

- Inspects repo evidence, performs approved implementation tasks, validates changed scope, and follows the declared authority hierarchy.

## Prompt Workflow

- Start from the user idea or ticket.
- Inspect the relevant code, artifacts, and current control files.
- Use `PROJECT_BRIEF.md`, `ARCHITECTURE.md`, `CURRENT_STATE.md`, `DECISIONS.md`, `TASK_QUEUE.md`, and `GUARDRAILS.md` to frame the task.
- Implement only after the task type and scope are clear.
- Validate the changed scope.
- Update project-control documents in later approved tasks when governance, architecture, decisions, or state have materially changed.

## Progress update protocol (semi-automatic)

- Trigger updates when all are true:
  - Task type is Implementation or Validation
  - Files changed affect mapped systems or loop components
  - Evidence exists for status/score wording change

- Do not update when any are true:
  - Task is Inspection or Planning only
  - Change is unrelated to mapped systems
  - Evidence is missing or ambiguous

## Evidence threshold

- Completion wording/score changes require implemented artifacts (code paths, outputs, schemas, or documented delivered milestone).
- Reliability wording/score changes require post-change run evidence from cycle artifacts/logs.
- If reliability evidence is not yet post-change, mark as pending baseline, not confirmed.

## Noise control

- Only edit roadmap fields that changed.
- Avoid broad rewrites of roadmap text for narrow fixes.
- Keep expectation updates limited to affected system sections.

## Legacy File Status

- `NOTES.md` is legacy planning notes and backlog material.
- `APP_PLAN.txt` is legacy planning and architecture reference material.
- These files remain useful as reference, but they are not authoritative project state.

## Boundaries

- `AGENTS.md` remains unchanged as the Codex behavior authority.
- `WORK_LOG.md` remains unchanged as append-only approved history.
- Legacy files are not deleted by this operating-system declaration; they are demoted to reference-only status unless deliberately migrated later.
