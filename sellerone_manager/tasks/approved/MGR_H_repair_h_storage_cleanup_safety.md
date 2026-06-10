# H Repair Package - Storage Cleanup Safety Proof - 2026-06-04

## Manager Authority
- task_id: MGR_H_repair_h_storage_cleanup_safety
- job_ref: H-STORAGE-CLEANUP-SAFETY
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Future work may inspect only H manager proof, cleanup receipts, and storage policy evidence: - `out/systems/M/hourly_mot_H.csv` - `out/systems/M/mot/mot_rollup_latest.md` - `out/systems/H/live/H_cleanup_ledger.jsonl` - `out/systems/H/staged` - `project_control/AGENT_NEW_CYCLE_STORAGE_RULES.md` - `project_control/EXPECTATIONS/H_cycle_expectations.md` - `sellerone_manager/hourly_mot.py`, only for read-only cleanup-proof classification - focused manager tests under `tests/manager/`, only if manager classification code changes - this package and `CODING_PLAN.md` for proof notes If a future source-level cleanup hook repair is needed, it must be split into a separate approved packet after the manager proves the exact source and boundary. This packet does not approve deletion.
- forbidden_actions: - Do not run H. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit local DB data. - Do not delete outputs. - Do not delete staged rollback snapshots. - Do not restart workers. - Do not hand-edit cleanup ledgers, MOT rows, manifests, terminal markers, or H outputs to make the warning disappear. - Do not widen into A, B, E, F, O, Product DB, scanner, supplier, or finance logic.
- proof_required: - Re-read the latest H MOT and confirm the warning still exists. - Inspect cleanup ledger shape and staged rollback counts from outside H only. - Confirm the newest rollback snapshots are preserved and the manager can explain which cleanup rule applies. - If only manager classification changes are made, compile touched manager files and run focused H manager tests. - Retest with the read-only H MOT. - Success means `h_storage_cleanup_safety` is `ok`, or remains an explicit non-blocking warning with rollback safety preserved and no hidden deletion risk.
- retest_command: ```powershell python -m sellerone_manager.app --hourly-mot --mot-flow H ```
- rollback_path: - Use git diff for manager-code rollback if any manager classification code changes. - Revert only manager proof wording or MOT classification code touched by the repair. - Do not delete H outputs, staged rollback snapshots, or cleanup ledgers as rollback.
- stop_condition: Stop immediately if the work would require H runtime execution, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, staged snapshot deletion, worker restart, or scope widening. Stop after the board-visible packet exists and the H manager can explain the cleanup warning without relying on chat memory.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_H_STORAGE_CLEANUP_SAFETY_PROOF_20260604
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_H_STORAGE_CLEANUP_SAFETY_PROOF_20260604.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_H_STORAGE_CLEANUP_SAFETY_PROOF_20260604",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_H_STORAGE_CLEANUP_SAFETY_PROOF_20260604.md"
}
```
