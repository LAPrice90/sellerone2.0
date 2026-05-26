# Single Stream Simplification Blueprint

## Date
- 2026-04-01 UTC

## Purpose
- Replace the current multi-owner runtime with a simpler single-stream operating model.
- Stop whack-a-mole fixes by removing overlapping control layers.
- Apply one consistent pattern across A, B, E, H and future flows.

## Executive Summary
- The current system has too many owners per loop (scheduler, launcher, supervisor, guarded wrappers, restart tools, maintenance logic, home-time logic).
- This creates race conditions, stale health evidence, and restart ambiguity.
- The fix is architectural simplification, not another local patch.
- The target is one owner path per flow, one health source per flow, one restart path per flow.

## Current Problem Report

### 1) Duplicate runtime ownership paths
- Evidence:
- `run_B_cycle.bat` launches `run_B_supervisor.py` which launches `run_B_cycle.py`.
- Scheduled task `AMZ Orders` is also a runtime owner.
- Additional restart tools can also influence ownership.
- Impact:
- Loop can be marked "running" while no real worker is active.
- Signals and task restarts can interrupt wrong layer and cause partial runs.

### 2) Multiple control systems with overlapping authority
- Evidence:
- Maintenance markers (`maintenance.requested`, `maintenance.ready`, `maintenance.active`).
- Restart gate/controller (`scripts/tools/controlled_restart_gate.py`, `scripts/tools/controlled_restart_controller.py`).
- Home-time mode (`start_home_time_mode.py`, `home_time_monitor.py`, stop tool).
- Impact:
- Ownership intent is unclear during incidents.
- Recovery actions can conflict.

### 3) Health truth split and stale interpretation
- Evidence:
- Global checklist, split checklists, runtime health outputs exist in parallel.
- Different files are fresh at different times (`checklist_H.csv`, `health_status_H.csv`, split files).
- Impact:
- Operators cannot quickly answer "is flow X healthy now?"
- Old evidence can be mistaken for current proof.

### 4) H publish freshness instability
- Evidence:
- H runtime can be `RUNNING` while publish/freshness checks show active fail conditions in shadow/live checks.
- H latest completed manifest can lag current runtime activity.
- Impact:
- "Loop up" is not equal to "sheet/output current".
- This is exactly the stale-sheet pain.

### 5) Complexity spread across all core flows
- Evidence:
- A/B/E/H have different handling for locks, health, restart, and gate semantics.
- Impact:
- Fixes are not reusable.
- Reliability improvements do not generalize.

## Simplification Target State (Single Stream Model)

### Design Principles
- One flow = one runtime owner.
- One flow = one health gate source.
- One flow = one restart mechanism.
- One flow = one lock contract.
- No control tool may directly own business runtime except the canonical launcher for that flow.

### Ownership Contract Per Flow
- A:
- Owner: `run_A_all.py` (manual or scheduler trigger only).
- No background supervisor.
- B:
- Owner: `run_B_supervisor.py` launched by one scheduler task.
- `run_B_cycle.py` is worker only, never separately scheduled.
- E:
- Owner: `run_E_cycle.py` triggered by A or explicit scheduler.
- No parallel owner.
- H:
- Owner: `run_H_pricing_cycle_guarded.py` launched by one scheduler task.
- `run_H_pricing_cycle.py` is worker only, never separately scheduled.

### Health Contract Per Flow
- A gate source: `out/cycle_alerts/checklist_A_split.csv`
- B gate source: `out/cycle_alerts/checklist_B.csv`
- E gate source: `out/cycle_alerts/checklist_E_split.csv`
- H gate source: `out/cycle_alerts/checklist_H.csv`
- Global checklist is observability only, not flow gate truth.

### Restart Contract Per Flow
- Standard restart action:
- stop owner
- confirm lock clear or stale lock recovered
- start owner
- confirm lock heartbeat
- confirm one completed run artifact
- No secondary restart layer may bypass this sequence.

## Phased Implementation Plan (Apply Today Start)

## Phase 0 - Freeze and Baseline
- Goal:
- Stop adding control complexity while simplification is underway.
- Code plan:
- Add a temporary "simplification freeze" guard in runtime control tools.
- Document canonical owner per flow in one machine-readable config.
- Files:
- `project_control/REPRICER_RUNTIME_CONTRACT.md`
- new: `config/runtime_owner_contract.json`
- Tests:
- `test_runtime_owner_contract_loads`
- `test_owner_contract_has_one_owner_per_flow`
- Gate to pass:
- Contract file exists, validates, and is referenced by launcher scripts.

## Phase 1 - Ownership Unification
- Goal:
- Enforce one runtime owner path for each flow.
- Code plan:
- B:
- keep scheduler -> `run_B_cycle.bat` -> `run_B_supervisor.py` -> `run_B_cycle.py`
- block direct worker starts from schedulers and helper tools.
- H:
- keep scheduler -> `run_H_cycle.bat` -> guarded wrapper -> worker
- block direct worker starts outside guarded path.
- Files:
- `run_B_cycle.bat`
- `scripts/cycles/run_B_supervisor.py`
- `run_H_cycle.bat`
- `scripts/cycles/run_H_pricing_cycle_guarded.py`
- Tests:
- `test_b_single_owner_chain`
- `test_h_single_owner_chain`
- `test_no_direct_worker_scheduler_targets`
- Gate to pass:
- Process tree proof shows exactly one owner chain per flow and no duplicate owner.

## Phase 2 - Control Layer Deconflict
- Goal:
- Remove overlapping authority between maintenance, restart controller, and home-time monitor.
- Code plan:
- Make restart tools observer-only unless explicit escalation flag is present.
- Prevent home-time monitor from acting as runtime owner.
- Restrict maintenance markers to A-B boundary only.
- Files:
- `scripts/tools/controlled_restart_gate.py`
- `scripts/tools/controlled_restart_controller.py`
- `scripts/tools/home_time_monitor.py`
- `scripts/tools/home_time_common.py`
- Tests:
- `test_restart_tools_observer_by_default`
- `test_home_time_never_claims_runtime_ownership`
- `test_maintenance_scope_a_b_only`
- Gate to pass:
- No automatic restarter can stop/start B or H without explicit escalation mode.

## Phase 3 - Health Signal Simplification
- Goal:
- Make gate truth unambiguous.
- Code plan:
- Enforce one gate file per flow.
- Mark all other health files as observability-only in code and logs.
- Ensure freshness checks use flow-owned gate first.
- Files:
- `scripts/flows/A/A015_build_system_health_check.py`
- `scripts/cycles/run_A_all.py`
- `scripts/cycles/run_B_cycle.py`
- `scripts/cycles/run_E_cycle.py`
- `scripts/cycles/run_H_pricing_cycle.py`
- Tests:
- `test_flow_owned_health_gate_selection`
- `test_global_health_not_used_as_flow_gate`
- `test_gate_freshness_uses_flow_scope_first`
- Gate to pass:
- Gate decisions for A/B/E/H are reproducible from one file per flow.

## Phase 4 - Boundary and Resume Reliability
- Goal:
- Make A-B handoff and H publish-state transitions deterministic.
- Code plan:
- Keep A-B maintenance request-ready-active-clear as the only supported handoff.
- Harden post-handoff resume verification.
- Add explicit H publish freshness checkpoints and fail-closed terminal markers.
- Files:
- `scripts/cycles/run_A_all.py`
- `scripts/cycles/run_B_cycle.py`
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/flows/H/H110_run_phase1_h_pilot.py`
- Tests:
- `test_a_b_maintenance_full_chain`
- `test_b_resumes_after_a_clear`
- `test_h_publish_checkpoint_chain`
- `test_h_terminal_marker_truth`
- Gate to pass:
- Controlled test run proves: A handoff complete, B resumes, H publish chain remains truthful.

## Phase 5 - Rollout Pattern to All Working Scripts
- Goal:
- Apply one standard runtime pattern to all active scripts.
- Code plan:
- Add a reusable runtime utilities module for:
- lock format and heartbeat
- owner lifecycle states
- restart proof steps
- health gate read helper
- Migrate active cycle scripts to shared utilities.
- Files:
- new: `scripts/core/runtime_stream.py`
- update: `scripts/cycles/*.py` (A/B/E/H first)
- Tests:
- `test_runtime_stream_lock_contract`
- `test_runtime_stream_lifecycle_contract`
- `test_runtime_stream_restart_proof_contract`
- Gate to pass:
- All core flows use shared contract functions with matching behavior.

## Cross-Phase Test Strategy

### Test categories required between every phase
- Unit tests:
- Logic and contract checks.
- Integration tests:
- Cross-file flow behavior inside one flow.
- Runtime smoke tests:
- Owner starts, lock heartbeat advances, one run finalizes.
- Recovery tests:
- owner interrupted, owner recovers without stale lock.

### Mandatory runtime proof bundle per phase
- Run IDs used.
- Owner process tree snapshot.
- Lock file content and heartbeat timestamps.
- Manifest final_state and timestamps.
- Flow-owned gate snapshot with fail/warn counts.

## Today Execution Plan (Practical)
- Step 1:
- Approve this blueprint as the implementation contract.
- Step 2:
- Execute Phase 0 and Phase 1 in this ticket.
- Step 3:
- Run runtime proof for B and H single-owner chains.
- Step 4:
- If proof passes, continue with Phase 2 and Phase 3 today.
- Step 5:
- Finish with a stop/go checkpoint for Phase 4 (boundary reliability).

## Risks and Mitigations
- Risk:
- Existing ad hoc tools depend on old ownership paths.
- Mitigation:
- Add compatibility warnings first, then hard-fail after one review window.
- Risk:
- Temporary warning spike while health gate semantics are tightened.
- Mitigation:
- Predefine expected transitional warns and expiry date in exception list.
- Risk:
- Unexpected scheduler behavior in Windows task state.
- Mitigation:
- Add explicit task-state plus process-tree checks as proof criteria.

## Definition of Done for Simplification Program
- Single owner per A/B/E/H confirmed.
- No duplicate runtime ownership events in last 10 runs per flow.
- Flow-owned health gate used consistently.
- A-B handoff and B resume chain proven.
- H publish freshness chain proven.
- No stale sheet incident across agreed observation window.

## Immediate Operator Rule During Migration
- No new runtime wrappers.
- No new restart tool hooks.
- No new health files for gate decisions.
- Any required change must map to this blueprint phases.
