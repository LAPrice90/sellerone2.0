# Project Brief

## Purpose

SellerOne 2.0 is an operations system for maintaining listing, stock, token, pricing, and health outputs with visible lineage, controlled publishing, and recoverable daily cycles.

## Confirmed Project Goals

- Keep system truth inside the repo rather than in chat history.
- Preserve manual business inputs instead of overwriting them with incomplete automation.
- Make freshness, failures, and recovery steps visible in artifacts and logs.
- Reduce stale-data risk by enforcing canonical read paths and clear source ownership.
- Keep operational flows understandable enough to recover after interruptions or incidents.

## Current Scope

- A flow covers health and supporting checks.
- B flow owns token and related operational outputs.
- H flow consumes operational data for pricing and seller-history style outputs.
- `project_control/` is the intended governance lane for project brief, architecture, state, decisions, task queue, and guardrails.

## Confirmed Principles From Legacy Planning

- Product data needs a single source-of-truth model, even where the current implementation still uses transitional layers.
- Manual fields and user-supplied business inputs must be protected.
- Staleness must be visible through timestamps, logs, or health outputs.
- Estimates and actuals should remain distinguishable rather than being silently merged.
- Missing external business data should be requested from the user, not invented.

## What This File Is For

- Define repo-level purpose and operating intent.
- Hold durable project goals that should outlive any one task.
- Point to other control files for implementation detail.

## What This File Is Not For

- Codex behavior rules. Those remain in `AGENTS.md`.
- Approved historical audit entries. Those remain in `WORK_LOG.md`.
- Fine-grained architecture decisions. Those belong in `DECISIONS.md`.
- Active task backlog detail. That belongs in `TASK_QUEUE.md`.

## Linked Control References

- Architecture baseline: `project_control/ARCHITECTURE.md`
- Current working snapshot: `project_control/CURRENT_STATE.md`
- Durable decisions: `project_control/DECISIONS.md`
- Open work and queued cleanup: `project_control/TASK_QUEUE.md`
- System rules and data-protection constraints: `project_control/GUARDRAILS.md`

## Needs Review

- Confirm whether the long-term product source of truth is still intended to move from sheet-backed operation to DB-backed publishing, or whether that legacy plan is now obsolete.
- Confirm whether the current flow naming and ownership model in the repo should replace the older A/B/C/D/E module framing from `APP_PLAN.txt`.
