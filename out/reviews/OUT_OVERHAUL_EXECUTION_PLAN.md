# Out Overhaul Execution Plan

## Objective
Eliminate loose root files in `out/` by migrating active writers/readers into owner folders while keeping cycles stable.

## Current State (2026-02-18)
- Root loose files still present: active runtime outputs.
- Safe archive passes completed.
- Runner control paths started (A/B/E/H launcher logs/locks/state).

## Hard Rule
- No direct file moves for active artifacts unless writer+reader paths are migrated first.

## Phase A - Visibility and Control (Done)
- [x] Create `out/systems/<A|B|E|H|shared>/{live,archive,todo}`
- [x] Archive obvious test/debug/manual clutter with rollback manifests
- [x] Add `out/reviews/OUT_STRUCTURE_POLICY.md`
- [x] Add `out/reviews/ROOT_ACTIVE_FILES.md`

## Phase B - Writer Migration (In Progress)
- [x] Move runner-owned logs/locks/state via launcher env vars:
  - A: `run_cycle.lock`
  - B: `B_cycle.log`, `B_cycle.lock`, state txt
  - E: `e_run_log.jsonl`, `e_decision_log.csv`
  - H: `H_cycle.log`, `H_pricing_cycle.log`, `H_pricing_cycle.lock`, `h_pricing_cycle_state.json`, `phase1_pilot_task.log`
- [ ] Restart launchers and confirm new writes land under `out/systems/*/live`
- [ ] Archive old root control files after confirmation

## Phase C - Flow Artifact Migration (Next)
### C1 B flow artifacts
- Target folder: `out/systems/B/live/`
- Migrate writer outputs for orders/token/order-master/orphan outputs.
- Add read fallback in health checks during cutover window.

### C2 H flow artifacts
- Target folder: `out/systems/H/live/`
- Migrate H market snapshots and floor traces.
- Keep legacy lookup fallback for one cycle window.

### C3 E flow artifacts
- Target folder: `out/systems/E/live/`
- Migrate E output files and consumer lookups.

### C4 Shared artifacts
- Target folder: `out/systems/shared/live/`
- Migrate financial and fee ledgers that are cross-flow shared.

## Phase D - Root Guard (Final)
- Add health check FAIL when unexpected loose files exist in `out/` root.
- Allowlist only root control folders and approved root files (if any).

## Verification Gates
- For each migration batch:
  1) writer path updated
  2) next cycle writes new path
  3) consumers read new path (or fallback)
  4) old root file archived with rollback manifest
- Final done:
  - no loose operational files in root
  - 10 consecutive runs with root guard pass

## Rollback
- Every archive batch includes:
  - `move_manifest.csv`
  - `rollback_moves.ps1`
