# Task Queue

## Purpose

This file is the draft project queue for unapproved or upcoming work that should move out of `NOTES.md` and other scattered planning files.

## Priority Queue

### Weekly Reset Execution Block (2026-03-17 to 2026-03-23 UTC)

- Must Do:
- Validate overnight restart end-to-end in one real overnight run (shutdown, reboot, auto-login, morning cycle recovery).
- Keep A -> E daily chain green and verify fresh A and E manifests each morning.
- Keep B live freshness stable (orders, order_master) and confirm no stale-running scheduler state.
- Keep H live stable with launcher ownership model and no churn-loop regression.
- Decide and document handling path for `h_parked_sku_write_attempts` WARN (event-time proof or approved exception).
- Should Do:
- Add event-time parked evidence so parked-write WARN can be promoted to deterministic pass/fail.
- Tighten daily runbook checks into a single morning-midday-evening checklist.
- Review one week of H runtime logs for interruption/reconcile drift.
- Nice To Have:
- Refresh progress chart wording to reflect "H stable enough for normal live use".
- Start backlog grooming for feeder/operations-loop work without pulling focus from stability.

### Governance Consolidation

- Populate `project_control/OPERATING_SYSTEM.md` so the new control lane has a clear narrative operating model.
- Review the drafted `project_control` files and approve which legacy files can be demoted to reference-only.
- Plan a later migration task to retire active planning use of `NOTES.md` and `APP_PLAN.txt` without deleting history.

### H Stability Ghosts - Control Simplification Plan (PROMPT 022)

- Stage 1 - disable duplicate restart authorities:
- enforce one active restart owner window for H
- move non-owner layers to observe-only or escalation-only behavior
- Stage 2 - anti-churn relaunch policy:
- replace fixed rapid relaunch pattern with cooldown-aware behavior
- add repeated-short-failure guardrail
- Stage 3 - lock and heartbeat tolerance hardening:
- increase stale tolerance windows
- delay stale cleanup until reconcile window expires
- Stage 4 - interruption-aware handling:
- classify SIGBREAK/session-like exits as interruption class
- prevent rapid looped relaunch during interruption windows
- Stage 5 - controlled validation:
- run controlled H sessions and verify reduced relaunch churn
- verify no multi-authority overlap in restart decisions

### Canonical Source Enforcement

- Continue safe compat-mapped reader cleanup outside unresolved ownership areas.
- Add narrow guardrail checks to catch new hardcoded reads of compat-mapped live datasets.
- Resolve ownership for the decision-required datasets identified in `project_control/CANONICAL_ENFORCEMENT_PLAN.md` before attempting broader rewiring.

### Repricer Governance And Cleanup

- Formalize repricer document roles so one document defines the current live repricer contract and one defines the target repricer architecture.
- Reconcile repricer drift between:
- single-SKU Phase 1 wording and multi-SKU live reality
- `strategy-steps-v1.3.md` and `masterplan_v10.md`
- stock-source priority wording and implemented order
- ceiling fallback and CPT wording
- writer-mode/config authority
- file naming and terminology
- Add a repricer capability matrix to project-control so live, partial, deferred, and target-only areas are visible without rereading all process-guide documents.

### Repricer Product Sequence

- After H runtime stability is fixed separately, complete repricer planning cleanup before starting additional repricer feature work.
- Best next repricer feature candidate after planning cleanup:
- finish suppressed Buy Box fallback policy so suppression handling matches current architecture direction and live behavior expectations
- Suppressed Buy Box fallback completion should be staged as:
- define current-contract suppression policy and decision order
- align persistence and audit outputs
- add retry-budget, cooldown, stop, and ceiling-floor guardrails
- add validation and contract coverage
- Follow-on repricer product work after suppression cleanup:
- refine slow-bleed policy and inventory-pressure handling
- then plan portfolio and notification architecture as a separate later stage
- Keep these later-stage items deferred until the current runtime contract is cleaned up:
- pressure workflow
- demand learning
- broader portfolio governor behavior

### Suppression Fallback Completion Plan

- Must-have scope:
- define suppression entry, direct-target preference, learned-threshold use, inferred-upper-bound use, carry-forward use, and downward-probe rules
- define retry-budget, cooldown, stop, and re-entry rules
- add resolved-state audit outcomes to suppression outputs
- ensure persisted suppression ceilings are re-clamped to anchor-floor governance before storage
- Should-have scope:
- add contract checks for suppression decision order and persistence guardrails
- add output-level checks for stale temporary ceilings and repeated suppression loops
- update runtime and strategy documents so suppression wording matches live behavior
- Deferred scope:
- richer suppression learning models
- notification-led suppression handling
- portfolio-aware suppression policy
- demand-learning extensions tied to suppression recovery

### Data And Product Backlog Carried From Legacy Notes

- Add missing-SKUs warning to A003 run status when inventory rows are lower than active listings.
- Add a sales-linked sanity check for stock drops that exceed recent sales.
- Consider per-SKU inventory fetch fallback logging so failures are visible at SKU level.
- Build or formalize the Product DB manual field scaffold if that design is still current.
- Clarify fees strategy so actual posted fees supersede estimates without losing estimate visibility.
- Revisit refund handling, returns tracking, and inbound transportation fee allocation when those areas are approved for work.
- Review the SKU fee override cases noted in `NOTES.md`.

## Decision-Required Queue

- Decide whether Product DB sheet-first architecture is still the intended canonical business layer or whether a different long-term authority model now applies.
- Decide which unresolved duplicate-truth datasets should be canonical before any non-safe rewiring begins.
- Decide how much of the repo-wide operating model should migrate from `AGENTS.md` into `project_control/OPERATING_SYSTEM.md`.
- Confirm the repricer runtime-contract authority split:
- current live contract = `strategy-steps-v1.3.md`
- target architecture = `masterplan_v10.md`
- Confirm whether `config/h_sku_switches.csv` fully replaces `config/phase1_writer_modes.csv` for repricer write authority.
- Approve the suppressed Buy Box fallback completion policy for the current live repricer contract before code changes begin.

## Reference Sources For This Queue

- `project_control/CANONICAL_ENFORCEMENT_PLAN.md`
- `project_control/GOVERNANCE_AUDIT.md`
- `NOTES.md`
- `APP_PLAN.txt`
