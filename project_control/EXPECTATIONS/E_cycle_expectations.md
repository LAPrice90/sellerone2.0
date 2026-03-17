# E Cycle Expectations

## Purpose
The E cycle is the analytics layer that converts core operational data into decision-ready outputs for performance and restock planning.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| E cycle runner | E cycle executes defined analytics sequence | In Progress | `run_E_cycle.py` orchestrates E001-E005 |
| Sales velocity output | Velocity metrics are produced | In Progress | Implemented in E001 |
| ROI snapshot output | ROI snapshots are produced | In Progress | Implemented in E002 |
| Restock signal output | Restock signal table is produced | In Progress | Implemented in E003 |
| Performance summary output | Consolidated performance table is produced | In Progress | Implemented in E004 |
| Study report output | Study-style ranking report is produced | In Progress | Implemented in E005 |
| Cadence control | E cadence skip/run behavior works as designed | In Progress | Cadence guard exists in orchestrator |
| Optional publishing path | E outputs can be published when enabled | In Progress | E010 exists with gated sheet writes |
| Health profile evidence | E reliability evidence path is defined | In Progress | Profile/split checklist path exists but baseline still maturing |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed E runs:
- Fails: nonzero run, missing required output, or hard gate block.
- Warnings: stale evidence, degraded publish behavior, or profile warning outcomes.
- Clean runs: all core outputs present, run succeeds, and evidence is current.

Suggested scoring baseline:
- Start at 100.
- Subtract 20 if any fail exists in window.
- Subtract 5 per warned run, up to 30.
- Reliability is "To Baseline" until 10 comparable runs are available.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- E consistently produces velocity, ROI, restock, and performance outputs used by operations.
- Core outputs are fresh and available at expected cadence.
- Stable:
- No fail in last 10 runs.
- At least 8 of last 10 runs are clean.
- No persistent stale-evidence condition.
- Ready for expansion:
- Stable across 2 review windows.
- Additional analytics can be added without breaking core outputs.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Advanced ranking and prioritization models.
- Richer country-level and channel-level analytics.
- Additional visualization and dashboard formatting.
- Non-critical publish and reporting enhancements.
