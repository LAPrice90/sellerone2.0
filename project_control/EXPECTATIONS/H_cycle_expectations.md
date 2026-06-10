# H Cycle Expectations

## Purpose
The H cycle is the live repricing runtime. It collects market signals, applies repricing logic, and publishes pricing outcomes while preserving safety evidence.

## SECTION 1 - Completion Definition
| Feature | Description | Status | Notes |
|---|---|---|---|
| H launcher and guard runtime | H runs through approved launcher and guarded wrapper | In Progress | `run_H_cycle.bat` and guarded core are implemented |
| Offer and market collection | Offer snapshot and market data collection are active | In Progress | Snapshot and item/own offer lookup stages exist |
| Repricing decision logic | Repricing decisions are executed for scoped SKUs | In Progress | H110 and phase1 stack are implemented |
| Publish updates | Publish markers and runtime status outputs are written | In Progress | Publish and finalizer markers exist |
| Runtime lock safety | Lock ownership and overlap protections are active | In Progress | Lock, heartbeat, and ownership checks are implemented |
| Boundary truth handling | H to A016 boundary outcomes are captured safely | In Progress | Boundary artifacts exist, stabilization still needed |
| 10-run reliability window | Last 10 completed H runs are classified from outside proof as clean, warning, or failed | In Progress | `h_reliability_window` keeps latest-run readiness separate from longer stability |
| Health reporting | H health and runtime status artifacts are produced | In Progress | H health checklist and runtime status files are present |
| Storage self-cleaning | H staged rollback folders are capped and reported through central housekeeping | In Progress | `out/systems/H/staged/*` keeps the newest 5 snapshots by registry policy; cleanup must run only at a safe H boundary |

## SECTION 2 - Reliability Measurement
Measure reliability over the last 10 completed H runs:
- Fails: nonzero exits, unresolved boundary states, finalize-blocked outcomes, or ownership release errors.
- Warnings: runtime warnings that do not block run completion but reduce trust.
- Clean runs: successful run with valid publish/finalize evidence and no boundary ambiguity.

Suggested scoring baseline:
- Start at 100.
- Subtract 25 if any boundary/finalization fail exists in window.
- Subtract 20 if any fail exists in health or runtime contract checks.
- Subtract 5 per warned run, up to 25.
- Reliability remains provisional until 10 comparable runs complete.

## SECTION 3 - Acceptance Criteria
- Replacement Complete:
- H provides basic like-for-like repricing behavior for current scope.
- H completion includes truthful publish/finalizer evidence and stable boundary handling.
- Stable:
- No boundary/finalization fail in last 10 runs.
- At least 8 of last 10 runs are clean.
- No unresolved run-ownership ambiguity.
- Ready for expansion:
- Stability maintained across 2 review windows.
- Core runtime no longer marked `Needs Stabilising`.

## SECTION 4 - Improvement Backlog
These do not affect Completion Score:
- Advanced suppression intelligence layers.
- Portfolio-level strategy extensions.
- Notification-led orchestration features.
- Demand-learning and pressure-policy enhancements.

## SECTION 5 - Planning Tolerance Gate
- This expectations file defines reliability quality targets. It is not an automatic planning-stop rule by itself.
- Planning and optimisation work may proceed when H scoped hard-block conditions are clear.
- Hard-block examples for H planning:
- active FAIL in H scoped gate
- required H runtime or ownership state not operational
- required publish path down when publish is required
- unresolved ownership/finalization mismatch for active run markers
- duplicate owner or crash-loop behavior that prevents normal operation
- Soft-block examples for H planning:
- accepted non-blocking WARN with explicit reason and review cadence
- provisional reliability label during observation window
- intermittent recoverable runtime faults that do not stop required H operation
- stale aggregate labels when newer H live evidence is available
- Soft-blocks must be reported and tracked, but do not by themselves stop planning.
