# E Cycle Expectations

## Purpose
The E cycle is the analytics layer that converts core operational data into decision-ready outputs for performance and restock planning.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| E cycle runner | E cycle executes defined analytics sequence | Manager-Proved | Latest independent E MOT proves the manifest completed E001-E007 plus E-scoped health/profile proof. Last 10 completed E manifests all completed 8/8 steps with 0 step failures. |
| Sales velocity output | Velocity metrics are produced | Manager-Proved | E MOT proves the velocity output is fresh, populated, and schema-checked. |
| ROI snapshot output | ROI snapshots are produced | Warning-Labelled | E MOT proves ROI output exists and is fresh, but coverage is only 41 of 161 SKUs, so missing ROI remains a confidence warning. |
| Restock signal output | Restock signal table is produced | Manager-Proved | E MOT proves restock signals are fresh, populated, and separated from business-ready reorder proof. |
| Performance summary output | Consolidated performance table is produced | Manager-Proved | E MOT proves the performance summary is fresh, row-count believable, schema-checked, and carries confidence/missing-proof labels. |
| Study report output | Study-style ranking report is produced | Manager-Proved | E MOT proves the study report is fresh, aligned with performance output, and explains blank or missing truth states. |
| Cadence control | E cadence skip/run behavior works as designed | Manager-Proved | E MOT proves recent successful cadence evidence and preserved skip/run decisions. |
| Optional publishing path | E outputs can be published when enabled | Not Verified | Optional publishing remains not_verified until Luke explicitly approves publishing proof. This is not required for E evidence support. |
| Health profile evidence | E reliability evidence path is defined | Manager-Proved | E scoped health/profile proof is current and tied to the latest E run; the 10-run baseline is now proved from existing manifests. |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed E runs:
- Fails: nonzero run, missing required output, or hard gate block.
- Warnings: stale evidence, degraded publish behavior, or profile warning outcomes.
- Clean runs: all core outputs present, run succeeds, and evidence is current.

Suggested scoring baseline:
- Start at 100.
- Subtract 20 if any fail exists in window.
- Subtract 5 per warned run, up to 30.
- Reliability is "To Baseline" until 10 comparable runs are available. As of the 2026-06-04 manager review, 10 comparable completed E manifests are available and all 10 completed cleanly from the E run side.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- E consistently produces velocity, ROI, restock, and performance outputs used by operations.
- Core outputs are fresh and available at expected cadence.
- Stable:
- No fail in last 10 runs.
- At least 8 of last 10 runs are clean.
- No persistent stale-evidence condition.
- Current manager status: Stable as an evidence layer, with warnings still visible for ROI coverage and remaining upstream B money proof gaps. B067 now proves refund money, commission, FBA fee, and shipping income, but Sellerboard return-gap evidence is still bridge-only and shipping cost/chargeback is not yet proven.
- Ready for expansion:
- Stable across 2 review windows.
- Additional analytics can be added without breaking core outputs.
- Current manager status: Not yet proven for buying authority. E remains evidence support only until ROI coverage and the remaining upstream B money proof gaps are clean enough.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Advanced ranking and prioritization models.
- Richer country-level and channel-level analytics.
- Additional visualization and dashboard formatting.
- Non-critical publish and reporting enhancements.

## SECTION 5 - Planning Tolerance Gate
- This expectations file defines reliability quality targets. It is not an automatic planning-stop rule by itself.
- Planning and optimisation work may proceed when E scoped hard-block conditions are clear.
- Hard-block examples for E planning:
- active FAIL in E scoped gate
- required E run path not operational
- required E outputs stale beyond cadence
- required publish path down when publish is in scope
- Soft-block examples for E planning:
- accepted non-blocking WARN with reviewed reason
- "To Baseline" reliability label while run baseline is still building
- stale aggregate labels that lag newer E run evidence
- Soft-blocks must be reported and tracked, but do not by themselves stop planning.
