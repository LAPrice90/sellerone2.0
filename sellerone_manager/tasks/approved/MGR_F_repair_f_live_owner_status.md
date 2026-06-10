# F Repair Package - DHB Forward Progress Stall - 2026-06-06

## Manager Authority
- task_id: MGR_F_repair_f_live_owner_status
- job_ref: F-DHB-FORWARD-PROGRESS
- status: approved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py` - `scripts/flows/F/F061_run_legacy_first_checks_local.py` - `scripts/flows/F/_scanner_state.py` - focused F scanner tests under `tests/` - `sellerone_manager/hourly_mot.py` and focused manager tests only if the manager proof wording needs a narrow adjustment - this repair package and `plans/active/f-price-list-process-manager-v1/CODING_PLAN.md` for proof notes
- forbidden_actions: - Do not run F061. - Do not restart FPM or F061. - Do not edit F061 queue state. - Do not switch the active supplier manually. - Do not approve scanner handoff. - Do not rewrite active scanner output rows to make progress look better. - Do not fetch Gmail, download supplier files, or delete supplier files. - Do not write Google Sheets. - Do not change prices. - Do not align local DB facts. - Do not delete outputs. - Do not open a separate Chrome login window. - Do not widen into A, B, E, H, or O work.
- proof_required: - Add or adjust scanner tests so repeated `scanner_chunk` success rows with no pending-count drop cannot be treated as clean progress. - Add or adjust scanner tests so `f061_memory_import` blocked evidence cannot leave the live owner reporting clean success. - If the right behaviour is to park/reclassify the DHB tail row, prove it through code-level tests first. - Retest the manager layer with `python -m sellerone_manager.app --hourly-mot --mot-flow F`. - Live proof can happen only through a separate approved F proof window. Until then, the MOT failure should stay visible.
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: - Use git diff for code rollback. - Do not edit F queue files or scanner outputs during rollback. - Rerun the read-only F MOT after rollback.
- stop_condition: Stop immediately if the fix requires a live scanner run, scanner restart, queue edit, supplier switch, output rewrite, separate browser login, Sheet write, price change, local DB alignment, output deletion, or business judgement. Stop successfully when code-level proof prevents the DHB no-progress loop from being called healthy, and F MOT continues to show the live scanner truth without hiding the active failure.

## Source
- source_type: repair_package
- source_id: F_REPAIR_PACKAGE_F_DHB_FORWARD_PROGRESS_STALL_20260606
- source_path: plans\active\f-price-list-process-manager-v1\F_REPAIR_PACKAGE_F_DHB_FORWARD_PROGRESS_STALL_20260606.md

## Exact Source Row
```json
{
  "source_id": "F_REPAIR_PACKAGE_F_DHB_FORWARD_PROGRESS_STALL_20260606",
  "source_path": "plans\\active\\f-price-list-process-manager-v1\\F_REPAIR_PACKAGE_F_DHB_FORWARD_PROGRESS_STALL_20260606.md"
}
```
