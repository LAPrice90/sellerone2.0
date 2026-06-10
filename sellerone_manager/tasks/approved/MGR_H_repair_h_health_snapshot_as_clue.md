# H Classification Package - WARN Only State - 2026-05-30

## Manager Authority
- task_id: MGR_H_repair_h_health_snapshot_as_clue
- job_ref: H-CLASSIFICATION-ONLY-2026
- status: parked
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Future work from this package may inspect only manager proof and H warning evidence: - `out/systems/M/hourly_mot_H.csv` - `out/systems/M/mot/mot_rollup_latest.md` - `out/systems/M/mot/mot_worklist.csv` - `out/cycle_alerts/checklist_H.csv` - `out/systems/H/live/H_cleanup_ledger.jsonl` - `project_control/EXPECTATIONS/H_cycle_expectations.md` - `sellerone_manager/blueprints/H_CYCLE_BLUEPRINT.md` - this package and `CODING_PLAN.md` for manager proof notes If code work is later approved, it may touch only manager/MOT classification code needed to keep old checklist clues and cleanup warnings visible. It must not change H repricing behavior.
- forbidden_actions: - Do not run H. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit local DB data. - Do not delete outputs or staged rollback snapshots. - Do not restart workers. - Do not hand-edit manifests, terminal markers, MOT rows, health rows, or H outputs to improve the status. - Do not widen into A, B, E, F, O, Product DB, scanner, supplier, or finance logic.
- proof_required: - Re-read the latest H MOT and confirm H remains warning-only before changing any manager proof code. - Keep `h_health_snapshot_as_clue` as clue evidence only unless newer runtime proof agrees that it is a real current failure. - Keep `h_manager_readiness` as a summary row. Do not repair it directly. - If classification wording or MOT manager logic changes, run focused manager tests and then retest with the read-only H MOT. - Success means H stays at `FAIL 0`, the old checklist clue does not override newer runtime proof, and the storage warning stays visible until rollback safety is independently clear.
- retest_command: The read-only manager retest command is: ```powershell python -m sellerone_manager.app --hourly-mot --mot-flow H ``` Success for this package means: - H fail_count stays 0 - h_manager_readiness remains ok or warn, not fail - any storage cleanup work remains warning-level unless rollback proof is missing
- rollback_path: - Use git diff for any manager proof wording or MOT classification code rollback. - Do not delete H outputs or staged rollback snapshots as rollback. - Re-run the read-only H MOT after rollback if manager code changed.
- stop_condition: Stop this classification package after the H WARN-only state is recorded and the manager task can be marked proved. Do not continue into live H repair from this package.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot_20260530_warns
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot_20260530_warns.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot_20260530_warns",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot_20260530_warns.md"
}
```
