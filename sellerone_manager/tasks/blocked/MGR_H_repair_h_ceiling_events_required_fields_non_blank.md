# H Repair Package - Current Active Failures - 2026-05-27

## Manager Authority
- task_id: MGR_H_repair_h_ceiling_events_required_fields_non_blank
- job_ref: H-ACTIVE-FAILURES-2026-03
- status: blocked_needs_luke
- authority: standing_safe_code_repair
- luke_action_required: 1

## Boundary
- allowed_scope: Future repair may inspect and edit only files directly responsible for H output construction, H checklist mapping, or H proof planning, such as: - H worker scripts that build or write out/h_ceiling_events.csv. - H worker scripts that build or write out/listing_offer_snapshot_latest.csv. - H worker scripts that merge market context into listing offer snapshots. - H-scoped schema or validation helpers used by those H outputs. - H-scoped tests or one-off proof-planning files, if needed for isolated validation. - The active plan package or CODING_PLAN.md for recording proof windows and monitoring rules. Any future repair must first identify exact file paths from evidence before editing them.
- forbidden_actions: Do not do any of these inside this package or a future repair unless a separate manager-approved packet explicitly allows it: - Do not edit worker scripts during this packaging step. - Do not run H during this packaging step. - Do not run A015. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not change scheduler ownership. - Do not align or edit the local database. - Do not delete outputs. - Do not update approved task status. - Do not widen repair into A, B, E, F, O, or unrelated manager coverage.
- proof_required: A future repair is not proved by code edits alone. Required proof chain: - Make the smallest source-level fix inside H-owned code. - Run an isolated local validation for the touched builder or helper, if one exists. - Plan a guarded H proof window before live validation. - Use the H-owned proof path, not A015 alone. - Confirm the H run reaches a terminal marker after the change. - Confirm publish/finalizer truth is written after the change. - Read the refreshed H checklist only after the H run finalizes. - Success means both checks are no longer FAIL: - h_ceiling_events_required_fields_non_blank - h_market_context_fill_nonzero
- retest_command: No retest command was run for this packaging task. Future repair retest must use the manager-approved H proof path. The candidate command must be documented before execution with: ```powershell python scripts/one_off/P002_plan_forced_proof_window.py --flow h ``` After the proof window is approved and safe, the future repair batch should run the guarded H controlled one-shot or scheduler-owned H proof specified by the generated plan. Do not use A015 alone as proof.
- rollback_path: This package created only a new markdown planning file, so no worker rollback is needed. Future repair rollback must include: - Keep a copy or git diff of every edited H source file before repair. - Restore only the files changed by the repair batch if proof fails. - Do not delete business outputs as rollback. - Do not hand-edit proof CSVs to hide failures. - Re-run the same H-owned proof path after rollback if a live repair was attempted.
- stop_condition: Stop this package after the current H active failures, repair boundaries, proof path, rollback path, and Luke-decision status are recorded. Stop any future repair immediately if: - The root cause points outside H scope. - Repair would require price changes. - Repair would require queue edits. - Repair would require Google Sheets writes. - Repair would require scheduler ownership changes without explicit approval. - Repair would require local DB alignment or edits. - H ownership is active and no safe guarded proof window exists. - Evidence shows the two active FAIL checks do not match the package assumptions.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli_20260527_current_failures
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli_20260527_current_failures.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli_20260527_current_failures",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_MGR_H_repair_out_cycle_alerts_checkli_20260527_current_failures.md"
}
```
