# Guardrails

## Purpose

This file holds durable project and system guardrails. It is not the place for Codex-only workflow rules that already live in `AGENTS.md`.

## Confirmed System Guardrails

- Protect manual business-input fields from blank or guessed overwrites.
- Keep estimates and actuals distinguishable, and prefer actuals only where actual data is present.
- Make staleness visible through timestamps, logs, health checks, or similar operational artifacts.
- Fix data problems at the earliest stage that owns them rather than masking them downstream.
- Keep one-off scripts and daily-loop scripts as separate operating lanes.

## Source-Of-Truth Guardrails

- Compat-mapped datasets should be read through the approved path-resolution mechanism instead of direct hardcoded legacy mirror paths.
- Mirror, preview, cache, or fallback artifacts should not become silent sources of truth.
- Any future source rewrite should identify one clear writer owner and one clear preferred read path.
- Duplicate-truth groups must be documented before rewiring changes are made.

## Governance Guardrails

- `AGENTS.md` remains the Codex behavior authority unless a later approved migration changes that on purpose.
- `WORK_LOG.md` remains append-only approved history and should not be replaced by snapshot summaries.
- `CURRENT_STATE.md` should summarize current position only and avoid becoming a second historical ledger.
- `TASK_QUEUE.md` should become the main project backlog so `NOTES.md` can be demoted later.

## Recovery And Operations Guardrails

- Process-critical flows should have maintained runbooks or recovery notes rather than relying on chat memory.
- Operational recovery rules that affect system safety should be promoted into maintained control docs or runbooks when confirmed.
- Health and schema checks should be attached to new outputs or phases so issues surface close to the source.

## Needs Review

- Confirm which manual fields remain protected in the current system beyond the legacy list in `APP_PLAN.txt`.
- Confirm which guardrails should later be duplicated or summarized in `project_control/OPERATING_SYSTEM.md`.
- Add explicit canonical-read enforcement rules here after the planned guardrail task is approved.
