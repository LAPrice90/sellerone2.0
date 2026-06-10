# SellerOne Manager Control Plane V1 - Plan

## Summary
Build the manager as a same-repo, separate Python package at `sellerone_manager/`.

The manager is like a foreman walking around a factory floor with a clipboard. It does not operate the machines in v1. It checks the machine status labels, queue labels, and warning labels, then writes one simple report about what is really stopping work.

## Implementation
- Add `config/manager/modules/F_price_list_manager.json` as the first module manifest.
- Add manager manifests for selected F price-list manager scripts only after ranking proves priority.
- Add manager manifests for A, B, E, H, and O.
- Add expectation reconciliation in rollout order: A -> B -> E -> H -> F -> O.
- Add task-control-first outputs that classify issues and create manager task candidates without dispatching workers.
- Add standard-library Python readers for F live status, F dashboard, storage drift evidence, due checks, cycle summary, runtime owner contract, and script inventory.
- Write manager-owned outputs under `out/systems/M/`.
- Add a self-organisation guard that compares worker-like F scripts in `project_control/SCRIPT_INVENTORY.csv` against manager manifests.
- Keep all worker action permissions disabled in v1.

## Output Contracts
- `f_price_list_manager_snapshot.csv`
- `f_price_list_manager_snapshot.json`
- `manager_health.csv`
- `manager_incidents.csv`
- `codex_repair_queue.csv`
- `codex_repair_events.csv`
- `self_organisation_gaps.csv`
- `self_organisation/latest_f_script_registration_report.csv`
- `self_organisation/latest_f_script_registration_report.json`
- `self_organisation/latest_f_self_organisation_report.md`
- `self_organisation/latest_f_manifest_priority_ranking.csv`
- `self_organisation/latest_f_manifest_priority_ranking.json`
- `self_organisation/latest_f_manifest_priority_report.md`
- `latest_f_price_list_manager_report.md`
- `flow_maintenance_state.csv`
- `flow_maintenance_state.json`
- `flow_expectation_reconciliation.csv`
- `manager_task_candidates.csv`
- `multi_flow_manager_health.csv`
- `latest_manager_control_report.md`

## Current Registered F Manifests
- `config/manager/modules/F_price_list_manager.json`
- `config/manager/modules/FPM170_supervise_live_cycle.json`
- `config/manager/modules/FPM129_storage_drift_guard.json`
- `config/manager/modules/FPM050_build_next_action_report.json`

## Current Registered Core Flow Manifests
- `config/manager/modules/A_cycle.json`
- `config/manager/modules/B_cycle.json`
- `config/manager/modules/E_cycle.json`
- `config/manager/modules/H_cycle.json`
- `config/manager/modules/O_operations_loop.json`

## Proof
- Compile the manager package and tests.
- Run focused pytest for manager manifest validation, stale artifact handling, storage drift classification, output schema checks, and command output writing.
- Run:
  - `python -m sellerone_manager.app --flow F_price_list_manager --read-only --write-report`
  - `python -m sellerone_manager.app --flow all --read-only --write-report`
- Confirm 0 manager execution errors.

## Later Upgrade Gate
Do not add job dispatching until v1 produces 3 useful read-only reports. Any later dispatcher must be flow-boundary aware and require approved safe actions.
