# Current State

## Purpose Of This Snapshot

This file is a concise present-tense summary of the repo's current governance and enforcement position. It is not a replacement for the append-only audit history in `WORK_LOG.md`.

## Governance State

- `AGENTS.md` remains the active binding authority for Codex behavior.
- `WORK_LOG.md` remains the canonical approved audit trail and historical state ledger.
- `project_control/` now contains active reports for data lineage, source authority, canonical enforcement planning, prompt workflow, and governance audit.
- The core project control files are now populated and active so project governance can move out of legacy root-level notes and planning files.
- System roadmap and progress tracker: `project_control/ROADMAP_SYSTEM_MAP.md`.

## Weekly Reset Snapshot (2026-03-17 UTC)

- A cycle: completing again and reaching full traversal.
- B cycle: running again with fresh order outputs.
- E cycle: triggering again from A flow.
- H cycle: stable enough for normal live use; still operationally complex.
- Restart sequence: escalation-window path is implemented and ready for overnight validation.
- Health state: FAIL checks cleared in latest snapshot.
- Remaining active warning:
- `h_parked_sku_write_attempts` is currently WARN (out-of-stock parked attempts, event-time parked proof not yet available).

## Blueprint State (Canonical Zone Set)

- Supplier Discovery: Planned, reliability `To Baseline`.
- Product Sourcing / Feeder: Planned, reliability `To Baseline`.
- Operations Loop: Planned, reliability `To Baseline`.
- Data / Intelligence: In Progress with mixed reliability; A/B/E are operational and H remains stability-gated.
- Portfolio Management: Planned, reliability `To Baseline`.
- System Governance: In Progress with provisional reliability.

## Data Authority State

- The repo has a documented data lineage map in `project_control/DATA_LINEAGE_REPORT.md`.
- The repo has a documented source authority classification in `project_control/SOURCE_AUTHORITY_REPORT.md`.
- The repo has a phased canonical enforcement plan in `project_control/CANONICAL_ENFORCEMENT_PLAN.md`.

## Enforcement Progress

- B-side readers of token live files have been rewired to use compat-resolved canonical live paths.
- Non-B readers of B token live files have been rewired to use compat-resolved canonical live paths.
- Safe H and health readers of compat-mapped legacy files such as `listing_offer_history.csv` and H probe logs have been rewired to prefer canonical H live paths.

## Repricer State

- The live repricer currently operates inside H flow rather than as an isolated subsystem.
- Repricer implementation exists across:
- `scripts/phase1/`
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`
- `scripts/flows/A/A016_refresh_phase1_daily_intel.py`
- `scripts/flows/A/A018_build_phase1_floor_table.py`
- The live repricer has moved beyond the original single-SKU Phase 1 plan and now runs against active-merchant scope with stock and parked filtering.
- Current live scope evidence:
- `out/phase1_sku_scope.csv` currently contains broad multi-SKU scope rather than pilot-only scope.
- The current runtime-contract reference is `out/process_guides/repricing_tool/strategy-steps-v1.3.md`.
- The current control-file runtime contract is `project_control/REPRICER_RUNTIME_CONTRACT.md`.
- The current target-architecture reference is `out/process_guides/repricing_tool/master plans/masterplan_v10.md`.

## Repricer Capability Position

- Complete or materially present:
- H and A orchestration for repricer operation
- daily intel and floor-table builders
- phase-engine persistence
- write gating and contract check
- suppression memory and reactivation outputs
- observation dashboard publishing
- Partial:
- broader phase-behavior rollout beyond the Phase 1 style decision path
- suppressed Buy Box fallback completion
- policy cleanup around slow-bleed and inventory-pressure behavior
- Not started or target-only:
- notification-led repricer runtime
- portfolio governor layer
- pressure workflow
- demand-learning architecture

## Repricer Governance Ambiguities

- The repricer now has identified planning drift that still needs cleanup:
- single-SKU Phase 1 language versus current multi-SKU reality
- v1.3 versus v10 document authority
- stock-source order wording
- ceiling fallback and CPT wording
- writer-mode/config authority
- file naming and terminology drift
- Project-control files now recognize the repricer as a governed subsystem, but the detailed conflict cleanup work is still pending.

## Suppression Fallback Position

- Suppression handling is already materially live:
- suppression detection
- suppression memory
- suppression-specific runtime state
- direct suppression target selection
- inferred upper-bound fallback
- temporary suppression ceilings
- reactivation logging
- longer suppression verification windows
- The missing layer is the formal policy contract for:
- multi-cycle decision order
- retry budget and cooldown
- stop and re-entry conditions
- resolution criteria and resolved-state audit trail
- anchor-floor-safe persisted suppression ceilings
- Suppression fallback completion is therefore a current-contract completion task, not a greenfield feature.

## Active Structural Ambiguities

- Legacy planning content still exists in `NOTES.md` and `APP_PLAN.txt` and has not yet been formally demoted or archived.
- Some dataset ownership questions remain unresolved and still require explicit decisions before broader rewiring.
- `project_control/OPERATING_SYSTEM.md` is populated, but additional operating narrative refinement is still pending.

## Evidence Sources For This Snapshot

- `project_control/GOVERNANCE_AUDIT.md`
- `project_control/DATA_LINEAGE_REPORT.md`
- `project_control/SOURCE_AUTHORITY_REPORT.md`
- `project_control/CANONICAL_ENFORCEMENT_PLAN.md`
- recent approved code changes already made for compat-mapped read enforcement

## Needs Review

- Confirm whether this file should start carrying a short "last reviewed" line in a later task.
- Confirm when legacy planning files can be demoted to reference-only after their remaining valid content is fully migrated.

## H Stability State (PROMPT 022 Planning Snapshot)

- Current H stability evidence is mixed-cause, not single-cause:
- Windows/session interruption signals are present
- runtime relaunch policy shows churn behavior in historical windows
- internal H child failures also exist
- Current planning decision is to simplify control:
- one restart authority active at a time
- other layers observe or escalate only
- Current state is planning-approved but implementation-pending:
- no runtime-code changes are included in this snapshot
- documentation now records target ownership and tolerance model for upcoming implementation tickets
