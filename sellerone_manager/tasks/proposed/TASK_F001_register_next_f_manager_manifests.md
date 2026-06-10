# Task

task_id: TASK_F001_register_next_f_manager_manifests

linked_goal_id: GOAL_F001_one_flow_maintenance_lane

title: Create manager manifests for the next three F Price List Manager scripts

worker_scope: Manager registration only. This task adds read-only manager manifests for FPM060_build_status_dashboard, FPM070_stage_f061_handoff, and FPM100_apply_f061_handoff so the manager can describe those scripts safely.

allowed_files:
- config/manager/modules/FPM060_build_status_dashboard.json
- config/manager/modules/FPM070_stage_f061_handoff.json
- config/manager/modules/FPM100_apply_f061_handoff.json
- sellerone_manager/current_state.json only if refreshed by the manager front door
- out/systems/M/* only if refreshed by the manager front door

forbidden_files:
- scripts/flows/F/price_list_manager/FPM060_build_status_dashboard.py
- scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py
- scripts/flows/F/price_list_manager/FPM100_apply_f061_handoff.py
- scripts/flows/F/F061_run_legacy_first_checks_local.py
- out/systems/F/inbox/supplier_price_list_active_run.csv
- out/systems/F/inbox/supplier_price_list_run_state.csv
- Google Sheets
- local database records
- pricing outputs
- any A, B, E, or H worker files

acceptance_checks:
- New manifest JSON files are valid JSON.
- Each manifest names the correct owner entrypoint and worker entrypoint.
- Each manifest is read-only from the manager's point of view.
- Forbidden actions include worker edits, worker runs, queue edits, Google Sheets writes, local DB alignment, pricing changes, and output deletion.
- Manager refresh completes with 0 manager execution errors.
- Self-organisation warning count should reduce for the registered F scripts, or the task must record exactly why it did not.

stop_condition: Stop after the F manifest registration proof. Do not continue into A, B, E, H, Product DB, Operations Loop, or scanner worker repair without Luke approving the next flow or next batch.

manager_notes: This is the first one-flow-at-a-time maintenance batch. It turns existing F scripts into manager-readable contracts, like adding inspection labels to machinery that already exists. It must not repair or run the machinery.
