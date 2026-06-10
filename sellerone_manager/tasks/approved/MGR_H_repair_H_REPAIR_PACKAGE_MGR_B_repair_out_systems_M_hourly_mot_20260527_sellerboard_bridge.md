# H Historical Board Cleanup - Misrouted B Marketplace Package

## Manager Authority
- task_id: MGR_H_repair_H_REPAIR_PACKAGE_MGR_B_repair_out_systems_M_hourly_mot_20260527_sellerboard_bridge
- job_ref: H-OUT-SYSTEMS-HOURLY
- status: parked
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `sellerone_manager/task_packets.py`, only if the manager later needs to reclassify or retire misrouted historical package names. - `sellerone_manager/task_board.py`, only if the board display needs to hide historical misrouted cards without losing audit history. - this package and manager progress notes, only for wording and status clarity. No H worker files are in scope.
- forbidden_actions: - Do not run H. - Do not run or restart B. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit local DB data. - Do not delete outputs. - Do not delete or rewrite historical proof files to hide the old card. - Do not restart workers. - Do not widen into live B recovery, live H repricing, Product DB, scanner, supplier, or finance logic.
- proof_required: - Refresh approved task packets. - Confirm this card remains parked or is migrated by manager board logic only. - Confirm current H status still comes from independent H MOT rows, not this historical package. - If manager code changes, run focused task-board/task-packet tests.
- retest_command: ```powershell python -m sellerone_manager.app --refresh-approved-tasks ```
- rollback_path: - Use git diff for manager packet/board wording rollback. - Do not edit H runtime outputs, B business outputs, manifests, MOT rows, local DB facts, or task history to hide this package.
- stop_condition: Stop after the board card is clearly marked as parked historical cleanup context, or sooner if any fix would require worker runtime, scheduler ownership, price, queue, Sheet, DB, output deletion, restart, or business-data action.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_MGR_B_repair_out_systems_M_hourly_mot_20260527_sellerboard_bridge
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_MGR_B_repair_out_systems_M_hourly_mot_20260527_sellerboard_bridge.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_MGR_B_repair_out_systems_M_hourly_mot_20260527_sellerboard_bridge",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_MGR_B_repair_out_systems_M_hourly_mot_20260527_sellerboard_bridge.md"
}
```
