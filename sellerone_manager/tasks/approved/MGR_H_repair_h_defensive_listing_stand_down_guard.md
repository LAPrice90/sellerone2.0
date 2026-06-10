# H Repair Package - Defensive Listing Stand-Down Guard - 2026-06-04

## Manager Authority
- task_id: MGR_H_repair_h_defensive_listing_stand_down_guard
- job_ref: H-DEFENSIVE-LISTING-STAND
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Future work may inspect and edit only the defensive-listing guard and manager proof: - `config/h_defensive_listing_protection.csv`, only for the B06 defensive-listing toggle fields approved in this package - `scripts/phase1/phase1_defensive_listing.py` - `scripts/phase1/phase1_main_loop.py`, only if the caller passes the wrong rival/current proof into the guard - `tests/test_phase1_defensive_listing.py` - `tests/test_phase1_main_loop.py` - `sellerone_manager/hourly_mot.py`, only if MOT proof visibility needs updating for this guard - focused H manager tests under `tests/manager/`
- forbidden_actions: - Do not run H manually. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit local DB data. - Do not delete outputs. - Do not restart workers. - Do not widen into F, A, B, E, O, Product DB, scanner, supplier, or finance logic.
- proof_required: - Add a test proving equal rival price returns normal H control with no write. - Add a test proving rival above us returns normal H control with no write. - Keep the existing test proving a rival strictly below us can undercut by 1p inside floor and ceiling. - Run focused defensive-listing tests. - Run focused H manager tests if MOT proof visibility changes. - Retest with the read-only H MOT. - Success means B06 defensive mode only writes when the rival is strictly below us, and equal/above/gone states produce normal H control proof.
- retest_command: ```powershell python -m sellerone_manager.app --hourly-mot --mot-flow H ```
- rollback_path: - Use git diff to revert only the defensive-listing guard and focused tests touched by this repair. - Do not edit H outputs, action logs, daily proof, or live price data as rollback.
- stop_condition: Stop immediately if the repair would require a live H run, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, worker restart, or scope widening.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_STAND_DOWN_GUARD_20260604
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_STAND_DOWN_GUARD_20260604.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_STAND_DOWN_GUARD_20260604",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_STAND_DOWN_GUARD_20260604.md"
}
```
