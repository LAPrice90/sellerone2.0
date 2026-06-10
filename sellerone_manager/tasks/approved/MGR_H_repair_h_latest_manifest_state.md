# H Repair Package - Current Independent MOT Failures - 2026-05-30

## Manager Authority
- task_id: MGR_H_repair_h_latest_manifest_state
- job_ref: H-INDEPENDENT-FAILURES-2026-02
- status: parked
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: Future repair may inspect these evidence files: - out/systems/M/hourly_mot_H.csv - out/systems/M/hourly_mot_H.json - out/systems/M/mot/mot_worklist.csv - out/phase1_runtime_floor_snapshot_latest.csv - out/phase1_sku_scope.csv - out/h_floor_truth_trace.csv - out/listing_offer_history.csv - out/listing_offer_seller_observation_history.csv - out/systems/H/live/H_cycle_last_terminal_info.txt - out/systems/H/live/H_cycle_last_publish_info.txt - out/manifests/H/2026-05-30/H_20260530T190532Z.json Future repair may edit only the narrow H-owned source files that evidence proves are responsible, such as: - scripts/cycles/run_H_pricing_cycle.py - scripts/flows/H/H001_capture_offer_snapshot.py - scripts/flows/H/H002_build_phase1_seller_history.py - scripts/flows/H/H004_build_daily_market_snapshot.py - scripts/flows/H/H110_run_phase1_h_pilot.py - scripts/phase1/phase1_main_loop.py - scripts/phase1/phase1_storage.py - scripts/phase1/phase1_ceilings.py - scripts/h/h_floor_truth.py - scripts/h/h_floor_policy.py - focused H tests under tests/ - this package or the active CODING_PLAN.md, only for proof-window and monitoring notes Any future repair must first identify exact file paths from evidence before editing them.
- forbidden_actions: Do not do any of these inside this package or a future repair unless a separate manager-approved packet explicitly allows it: - Do not run H during this packaging step. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align or edit the local database. - Do not delete outputs. - Do not restart workers. - Do not run A015 as proof for this H repair. - Do not hand-edit MOT, checklist, manifest, runtime, or pricing outputs to make the row look fixed. - Do not widen repair into A, B, E, F, O, Product DB, scanner, or finance code.
- proof_required: A future repair is not proved by code edits alone. Required proof chain: - Confirm the active H MOT rows still match this package before editing. - Make the smallest source-level fix inside H-owned code. - Run focused isolated tests for the touched builder or helper. - Plan a guarded H proof window before live validation. - Use the H-owned proof path, not A015 alone. - Confirm the H run reaches a terminal marker after the change. - Confirm publish and finalizer truth are written after the change. - Confirm scheduler ownership restoration if scheduler ownership was paused in an approved proof packet. - Run `python -m sellerone_manager.app --hourly-mot --mot-flow H` after H finalizes. - Success means these rows are no longer FAIL: - h_latest_manifest_state - h_terminal_publish_truth - h_market_context_proof - h_floor_ceiling_safety_fields - h_boundary_finalizer_truth - h_manager_readiness
- retest_command: No live H retest was run for this packaging task. The read-only manager retest command for the package is: ```powershell python -m sellerone_manager.app --hourly-mot --mot-flow H ``` That command proves the manager layer can read the latest H truth. It is not enough by itself to prove a future H code repair unless a new H-owned proof run has finalized first.
- rollback_path: This package changed only manager planning records. Future repair rollback must include: - Keep a git diff or timestamped copy of every edited H source file before repair. - Restore only the files changed by the repair batch if proof fails. - Do not delete business outputs as rollback. - Do not hand-edit proof CSVs, manifests, or MOT rows to hide failures. - Re-run the same H-owned proof path after rollback if a live repair was attempted.
- stop_condition: Stop this package after the current H active failures, repair boundaries, proof path, rollback path, and Luke-decision status are recorded. Stop any future repair immediately if: - The root cause points outside H scope. - Repair would require a price change. - Repair would require a queue edit. - Repair would require a Google Sheets write. - Repair would require scheduler ownership changes without explicit approval and restore proof. - Repair would require local DB alignment or edits. - Repair would require output deletion. - H ownership is active and no safe guarded proof window exists. - Evidence changes so these active MOT failures no longer match the package assumptions.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_MOT_H_current_active_failures_20260530
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_MOT_H_current_active_failures_20260530.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_MOT_H_current_active_failures_20260530",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_MOT_H_current_active_failures_20260530.md"
}
```
