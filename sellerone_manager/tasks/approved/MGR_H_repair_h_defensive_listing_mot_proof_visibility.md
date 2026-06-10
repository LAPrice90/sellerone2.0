# H Repair Package - Defensive Listing MOT Proof Visibility - 2026-06-04

## Manager Authority
- task_id: MGR_H_repair_h_defensive_listing_mot_proof_visibility
- job_ref: H-DEFENSIVE-LISTING-VISIBILITY
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Future work may inspect and edit only manager proof recognition: - `sellerone_manager/hourly_mot.py` - `tests/manager/test_h_hourly_mot.py` - read-only proof files under `out/h_defensive_listing_action_log.csv` and `out/h_defensive_listing_daily.csv` - the H expectation file only if wording needs to reflect the proven proof surface
- forbidden_actions: - Do not run H manually. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit local DB data. - Do not delete outputs. - Do not restart workers. - Do not change defensive listing strategy logic in this proof-visibility package. - Do not widen into F, A, B, E, O, Product DB, scanner, supplier, or finance logic.
- proof_required: - Add or update H MOT tests so existing action/daily proof rows clear `live_enabled_waiting_proof`. - Confirm MOT reports B06 proof rows and live mode visibility accurately. - Retest with the read-only H MOT. - Success means the manager can see B06 defensive proof without relying on chat or raw file inspection.
- retest_command: ```powershell python -m sellerone_manager.app --hourly-mot --mot-flow H ```
- rollback_path: - Use git diff to revert only manager proof recognition and focused tests touched by this repair. - Do not edit H outputs, action logs, daily proof, or live price data as rollback.
- stop_condition: Stop immediately if the repair would require a live H run, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, worker restart, defensive strategy change, or scope widening.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_MOT_PROOF_VISIBILITY_20260604
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_MOT_PROOF_VISIBILITY_20260604.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_MOT_PROOF_VISIBILITY_20260604",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_H_DEFENSIVE_LISTING_MOT_PROOF_VISIBILITY_20260604.md"
}
```
