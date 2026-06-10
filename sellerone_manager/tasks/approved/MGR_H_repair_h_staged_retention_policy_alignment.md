# H Repair Package - Staged Retention Policy Alignment - 2026-06-04

## Manager Authority
- task_id: MGR_H_repair_h_staged_retention_policy_alignment
- job_ref: H-STAGED-RETENTION-POLICY
- status: parked
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Future work may inspect and edit only the source-policy proof needed to align H staged retention: - `scripts/cycles/run_H_pricing_cycle.py`, only the H staged-retention cap/proof-writing source - `project_control/log_housekeeping_registry.json`, only if evidence proves the manager registry rule is wrong - `project_control/EXPECTATIONS/H_cycle_expectations.md`, only for wording that reflects proven policy - focused tests for H storage cleanup proof and H retention policy - manager packet/status files needed to record proof This package does not approve deleting staged snapshots. If a proof step would require actual output deletion or a live H run, stop and return it as a protected approval decision.
- forbidden_actions: - Do not run H. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit local DB data. - Do not delete outputs. - Do not delete staged rollback snapshots. - Do not restart workers. - Do not widen into A, B, E, F, O, Product DB, scanner, supplier, or finance logic.
- proof_required: - Confirm the central registry cap and the H runtime cleanup receipt still disagree. - Repair only the source that writes or chooses the H staged-retention cap. - Add focused tests proving the manager cap and H receipt cap agree without running H or deleting snapshots. - Retest with the read-only H MOT. - Success means `h_storage_cleanup_safety` no longer reports a registry/runtime cap mismatch, or the task is blocked with a clear Luke decision if live deletion approval is required.
- retest_command: ```powershell python -m sellerone_manager.app --hourly-mot --mot-flow H ```
- rollback_path: - Use git diff to revert only the source-policy and manager-proof files touched by this repair. - Do not delete H outputs, staged rollback snapshots, or cleanup ledgers as rollback.
- stop_condition: Stop immediately if the repair would require H runtime execution, scheduler ownership change, publishing, price change, queue edit, Sheet write, local DB alignment, output deletion, staged snapshot deletion, worker restart, or scope widening.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_H_STAGED_RETENTION_POLICY_ALIGNMENT_20260604
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_H_STAGED_RETENTION_POLICY_ALIGNMENT_20260604.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_H_STAGED_RETENTION_POLICY_ALIGNMENT_20260604",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_H_STAGED_RETENTION_POLICY_ALIGNMENT_20260604.md"
}
```
