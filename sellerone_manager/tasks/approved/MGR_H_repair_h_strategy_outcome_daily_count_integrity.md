# H Repair Package - MGR_H_repair_out_cycle_alerts_checkli

## Manager Authority
- task_id: MGR_H_repair_h_strategy_outcome_daily_count_integrity
- job_ref: H-OUT-CYCLE-ALERTS
- status: parked
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - Read-only evidence files: - `sellerone_manager/tasks/approved/MGR_H_repair_out_cycle_alerts_checkli.md` - `out/cycle_alerts/checklist_H.csv` - `out/systems/M/approved_task_packets.csv` - `out/systems/M/manager_task_candidates.csv` - `out/systems/M/flow_expectation_reconciliation.csv` - `out/manifests/H/2026-05-26/H_20260526T184539Z.json` - `out/h_strategy_outcome_log.csv` - `out/h_strategy_outcome_daily.csv` - `project_control/EXPECTATIONS/H_cycle_expectations.md` - `project_control/ROADMAP_SYSTEM_MAP.md` - Repair-code candidates, only if the next repair batch is approved: - `scripts/phase1/phase1_main_loop.py` - `scripts/phase1/phase1_storage.py` - `scripts/one_off/H162_rebuild_strategy_outcome_daily.py` - focused H rollup tests under `tests/` - Repair-output candidates, only with timestamped backups first: - `out/h_strategy_outcome_daily.csv` - `out/h_strategy_outcome_log.csv` only if the approved repair explicitly needs source-log normalization, not just daily rebuild - Backup target for future repair: - `out/backups/h_strategy_outcome_daily_integrity/<UTC_TIMESTAMP>/`
- forbidden_actions: - Do not change prices. - Do not write Google Sheets. - Do not edit queues. - Do not change scheduler ownership. - Do not run H without an approved H proof window. - Do not hand-edit health outputs to make the FAIL disappear. - Do not manually edit `out/cycle_alerts/checklist_H.csv`. - Do not edit lock or ownership files, including H lock files and files under `out/locks/`. - Do not edit Product DB, local DB alignment files, or SQL migration state. - Do not edit F061 queue state or any F scanner queue files. - Do not edit A, B, E, F, or O worker scripts as part of this H package. - Do not change H publisher, price writer, or Amazon-write behavior unless Luke explicitly approves a wider H repair packet.
- proof_required: - Step 1 - preflight: - Confirm the active manager packet is still approved. - Confirm the H FAIL is still `h_strategy_outcome_daily_count_integrity`. - Confirm no H overlap or unsafe ownership condition exists before any repair proof. - Step 2 - isolated data proof: - Re-aggregate `out/h_strategy_outcome_log.csv` by `asof_date`, `scenario_type`, and `chosen_tactic`. - Confirm the failing group still proves the same mismatch. - Confirm the rebuilt daily row would satisfy: - `applied_rows + no_write_rows == decision_rows` - `resolved_rows + pending_rows == decision_rows` - `success_rows + failed_rows + expired_rows + aborted_rows <= decision_rows` - Step 3 - repair proof, if approved: - Create timestamped backups before any output write. - Use a generated rebuild path, not a hand edit, to rebuild the daily strategy summary from the source log. - If code is changed, run focused compile and H rollup tests. - Step 4 - flow-owned H proof: - Use guarded H isolation or scheduler-owned proof exactly as the manager packet requires. - Do not claim success from A015 or a mid-cycle read alone. - Confirm terminal truth after finalization. - Confirm publish truth after finalization. - Confirm the scoped H checklist no longer has `h_strategy_outcome_daily_count_integrity=fail`. - Step 5 - manager closure: - Mark the task `fixed_needs_retest` only after repair and isolated proof. - Mark the task `proved` only after manager/MOT evidence confirms the H FAIL cleared after the proper H proof window.
- retest_command: python -m pytest tests/test_phase1_storage.py tests/test_phase1_main_loop.py -q
- rollback_path: - Packaging rollback: remove this package file and leave the approved manager task packet unchanged. - Future repair rollback: - Restore timestamped backups of `out/h_strategy_outcome_daily.csv`. - Restore `out/h_strategy_outcome_log.csv` only if that file was changed by the approved repair. - Revert any code edits in the allowed repair-code candidate files. - Re-run the same isolated aggregation check to confirm the rollback returned files to the backed-up state. - No price rollback, Sheet rollback, scheduler rollback, or queue rollback should be needed because those actions are outside this package and forbidden.
- stop_condition: - Stop now because manager classification, task packaging, allowed files, forbidden files, proof path, rollback path, and Luke-decision state are recorded. - Stop future repair immediately if the required action crosses into prices, Sheets, queues, scheduler ownership, local DB alignment, output deletion, worker expansion, or a live H run without an approved proof window. - Stop future repair if the source log no longer reconciles to the daily mismatch described here; that would mean the root cause evidence changed.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli.md"
}
```
