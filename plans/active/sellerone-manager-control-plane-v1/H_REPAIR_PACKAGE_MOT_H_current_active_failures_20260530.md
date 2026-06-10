# H Repair Package - Current Independent MOT Failures - 2026-05-30

## Phase 5 Update - 2026-05-30T21:04:40Z
The current active H FAIL group described below has now cleared.

Latest read-only H MOT result:
- status: warn
- fail_count: 0
- warn_count: 3

Cleared rows:
- h_market_context_proof
- h_floor_ceiling_safety_fields
- h_manager_readiness no longer fails and now reports ready with warnings

Remaining warning rows are classified in:
- `plans/active/sellerone-manager-control-plane-v1/H_REPAIR_PACKAGE_MGR_H_classification_out_systems_M_hourly_mot_20260530_warns.md`

No H run, scheduler pause, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart was performed to clear this package.

## Manager Task
- Source packet: MGR_H_proof_gap_project_control_EXPECTAT
- Source proof: out/systems/M/hourly_mot_H.csv
- This package is planning and classification only.
- No H worker repair was performed in this packaging step.
- No H run, scheduler pause, publish, price change, queue edit, Sheet write, local DB alignment, output deletion, or worker restart was performed.

## Evidence Read
- out/systems/M/hourly_mot_H.csv
- out/systems/M/hourly_mot_H.json
- out/systems/M/mot/mot_worklist.csv
- project_control/EXPECTATIONS/H_cycle_expectations.md
- sellerone_manager/blueprints/H_CYCLE_BLUEPRINT.md

## Current Active H Fail Group
The read-only H MOT run at 2026-05-30T19:56:50Z confirms 3 active H FAIL rows and 2 H WARN rows.

| Check | Status | Latest value | Repair meaning |
|---|---:|---|---|
| h_market_context_proof | fail | priced_rows_missing_market_context=22 | Some current H rows have pricing or decision evidence without market context proof. |
| h_floor_ceiling_safety_fields | fail | blank_floor_rows=0;blank_ceiling_rows=27 | Some current H rows are missing ceiling proof. |
| h_manager_readiness | fail | not_ready;failed_checks=2 | This is the summary gate and should clear only after the source proof rows clear. |

Current OK rows:
- h_latest_manifest_state is ok: the newest manifest completed.
- h_terminal_publish_truth is ok: terminal and publish proof match the same run.
- h_decision_execution_rows is ok: decision rows and execution rows match.
- h_lock_and_heartbeat_state is ok: H ownership is readable and single-owner.
- h_boundary_finalizer_truth is ok: manifest and terminal proof show a finalized boundary.

Current WARN rows:
- h_health_snapshot_as_clue is warning only: old checklist evidence is a clue, not the manager truth.
- h_storage_cleanup_safety is warning only: cleanup proof exists, but the staged area is larger than expected.

## Root Cause Summary
H is not ready for broad autonomy.

Plain-English summary:
- The manager can now see H from the outside.
- The newest H run did reach a clean outside boundary.
- The remaining active problem is narrower: H has missing market-context proof and missing ceiling proof on some pricing rows.
- The old H checklist is no longer treated as the main truth. It is only a clue.
- The manager-readiness row is not a separate thing to fix. It clears only after the real source rows clear.

This is like a warehouse inspector saying: the delivery van arrived and signed in, but some boxes still have missing safety labels. The answer is not to pretend the whole delivery is ready. The answer is to fix the missing proof at source.

## Expected Repair Split
- Repair task 1: H market-context proof.
  - Find why 22 priced or decision rows are missing current market context proof.
- Repair task 2: H ceiling safety proof.
  - Find why 27 current H rows have blank ceiling proof.
- Repair task 3: H storage cleanup warning.
  - Keep warning-level only unless the staged area becomes unsafe or rollback proof is missing.

Treat these as one repair only if code evidence proves the same H source step caused them. Otherwise keep them separate.

## Allowed Files For A Future Repair Batch
Future repair may inspect these evidence files:
- out/systems/M/hourly_mot_H.csv
- out/systems/M/hourly_mot_H.json
- out/systems/M/mot/mot_worklist.csv
- out/phase1_runtime_floor_snapshot_latest.csv
- out/phase1_sku_scope.csv
- out/h_floor_truth_trace.csv
- out/listing_offer_history.csv
- out/listing_offer_seller_observation_history.csv
- out/systems/H/live/H_cycle_last_terminal_info.txt
- out/systems/H/live/H_cycle_last_publish_info.txt
- out/manifests/H/2026-05-30/H_20260530T193437Z.json

Future repair may edit only the narrow H-owned source files that evidence proves are responsible, such as:
- scripts/cycles/run_H_pricing_cycle.py
- scripts/flows/H/H001_capture_offer_snapshot.py
- scripts/flows/H/H002_build_phase1_seller_history.py
- scripts/flows/H/H004_build_daily_market_snapshot.py
- scripts/flows/H/H110_run_phase1_h_pilot.py
- scripts/phase1/phase1_main_loop.py
- scripts/phase1/phase1_storage.py
- scripts/phase1/phase1_ceilings.py
- scripts/h/h_floor_truth.py
- scripts/h/h_floor_policy.py
- focused H tests under tests/
- this package or the active CODING_PLAN.md, only for proof-window and monitoring notes

Any future repair must first identify exact file paths from evidence before editing them.

## Forbidden Files And Actions
Do not do any of these inside this package or a future repair unless a separate manager-approved packet explicitly allows it:
- Do not run H during this packaging step.
- Do not pause or resume scheduler ownership.
- Do not publish.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not align or edit the local database.
- Do not delete outputs.
- Do not restart workers.
- Do not run A015 as proof for this H repair.
- Do not hand-edit MOT, checklist, manifest, runtime, or pricing outputs to make the row look fixed.
- Do not widen repair into A, B, E, F, O, Product DB, scanner, or finance code.

## Proof Path For A Future Repair
A future repair is not proved by code edits alone.

Required proof chain:
- Confirm the active H MOT rows still match this package before editing.
- Make the smallest source-level fix inside H-owned code.
- Run focused isolated tests for the touched builder or helper.
- Plan a guarded H proof window before live validation.
- Use the H-owned proof path, not A015 alone.
- Confirm the H run reaches a terminal marker after the change.
- Confirm publish and finalizer truth are written after the change.
- Confirm scheduler ownership restoration if scheduler ownership was paused in an approved proof packet.
- Run `python -m sellerone_manager.app --hourly-mot --mot-flow H` after H finalizes.
- Success means these rows are no longer FAIL:
  - h_market_context_proof
  - h_floor_ceiling_safety_fields
  - h_manager_readiness

## Retest Command
No live H retest was run for this packaging task.

The read-only manager retest command for the package is:

```powershell
python -m sellerone_manager.app --hourly-mot --mot-flow H
```

That command proves the manager layer can read the latest H truth. It is not enough by itself to prove a future H code repair unless a new H-owned proof run has finalized first.

## Rollback Path
This package changed only manager planning records.

Future repair rollback must include:
- Keep a git diff or timestamped copy of every edited H source file before repair.
- Restore only the files changed by the repair batch if proof fails.
- Do not delete business outputs as rollback.
- Do not hand-edit proof CSVs, manifests, or MOT rows to hide failures.
- Re-run the same H-owned proof path after rollback if a live repair was attempted.

## Stop Condition
Stop this package after the current H active failures, repair boundaries, proof path, rollback path, and Luke-decision status are recorded.

Stop any future repair immediately if:
- The root cause points outside H scope.
- Repair would require a price change.
- Repair would require a queue edit.
- Repair would require a Google Sheets write.
- Repair would require scheduler ownership changes without explicit approval and restore proof.
- Repair would require local DB alignment or edits.
- Repair would require output deletion.
- H ownership is active and no safe guarded proof window exists.
- Evidence changes so these active MOT failures no longer match the package assumptions.

## Whether Luke Is Needed
Luke is not needed for this packaging task.

Luke is needed before any protected future action, including price changes, queue edits, Google Sheets writes, scheduler ownership changes without restore proof, local DB alignment or edits, output deletion, worker restart, or a live H run outside an approved proof window.
