# F061 Handoff Proof Plan

Date: 2026-04-30
Scope: Price-list process manager Phase 6 staged handoff.

## Boundary
This phase adds a guarded live-apply script, but the normal proof path remains preview-only until the user approves a safe F061 boundary.

Allowed now:
- build F061-shaped staged files under `out/systems/F/price_list_manager/test_mode/`
- check whether F061 is idle
- record or revoke explicit test-mode handoff approval for the exact supplier/batch
- prove live apply is blocked while F061 is busy
- build an apply preview with no live write
- create backups only inside an explicitly confirmed live-apply run

Not allowed now:
- replace `out/systems/F/inbox/supplier_price_list_active_run.csv` unless all guards pass and `--apply-live --confirm-approved-handoff` are both present
- replace `out/systems/F/inbox/supplier_price_list_run_state.csv` unless all guards pass and `--apply-live --confirm-approved-handoff` are both present
- start F061 automatically
- switch suppliers while F061 has pending rows

## Current F061 State
Observed on 2026-04-30:
- active supplier: `stocklist_supplier`
- run status: `running`
- pending active rows: `20316`
- running run-state rows: `1`
- pending run-state rows: `20316`

Decision:
- live handoff is blocked
- staged preview only is allowed
- approval is not enough while F061 is busy

## Staged Handoff Contract
The process manager writes these staged files:
- `out/systems/F/price_list_manager/test_mode/f061_handoff_staged_active_run.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_staged_run_state.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_preview.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_approvals.csv`

The staged active run must match the F061 active-run columns:
- run id
- supplier id
- supplier name
- row key
- supplier SKU
- barcode
- supplier title
- unit cost
- currency
- VAT rate
- pending scan status
- source seen time

## Current Staged Proof
Latest staged preview:
- built at: `2026-04-30T17:00:00Z`
- supplier: `Stax`
- batch: `stax_source_20260430T144700Z_eaf2df92f4e3`
- run id: `fpm_stax_20260430T170000Z`
- staged rows: `24231`
- technical ready flag: `0`
- approval state: `required`
- live apply allowed: `0`
- F061 idle status: `busy`
- block reason: `f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`

## Approval Gate
Technical readiness and approval are separate.

Technical readiness requires:
- active run has `0` pending rows
- run state has no `running` row
- run state pending rows total is `0`
- staged row count is greater than `0`
- all F061-required fields are present

Approval readiness requires:
- latest approval row matches the exact selected supplier and batch
- approval state is `approved`
- approval is not expired

Only when both are true may preview show:
- `technical_ready_flag=1`
- `approval_state=approved`
- `live_apply_allowed=1`

Current phase still refuses live apply even if the readiness preview becomes green.

## Guarded Apply Contract
The process manager can now build an apply preview:
- `out/systems/F/price_list_manager/test_mode/f061_handoff_apply_preview.csv`

The process manager also records backup evidence when a confirmed live apply is run:
- `out/systems/F/price_list_manager/test_mode/f061_handoff_apply_backups.csv`
- `out/systems/F/price_list_manager/test_mode/f061_handoff_backups/<backup_id>/manifest.csv`

Apply readiness requires:
- latest staged preview exists
- staged row count matches the preview
- staged run-state count matches the preview
- staged rows are all `pending`
- `technical_ready_flag=1`
- `approval_state=approved`
- `live_apply_allowed=1`
- F061 is still idle at apply time

Current apply preview:
- built at: `2026-04-30T17:15:00Z`
- supplier: `stax`
- staged rows: `24231`
- apply ready flag: `0`
- live write attempted: `0`
- live write succeeded: `0`
- block reason: `technical_ready_flag_not_1;approval_state_not_approved;live_apply_allowed_not_1;f061_not_idle:pending_active=20116;running_state=1;pending_state=20116`

## Forced Proof Sequence Later
Only use this when the user approves a live handoff test and F061 is idle.

1. Confirm F061 idle:
   - active run has `0` pending rows
   - run state has no `running` row
   - run state pending rows total is `0`
2. Stage the selected manager batch.
3. Confirm `technical_ready_flag=1`.
4. Record approval for the exact supplier and batch.
5. Rebuild staged preview and confirm `live_apply_allowed=1`.
6. Snapshot current live F061 input files.
7. Run `FPM100_apply_f061_handoff.py --apply-live --confirm-approved-handoff`.
8. Confirm backup manifest exists and live F061 active/run-state row counts match staged row counts.
9. Start or resume F061 only through the approved F061 owner path.
10. Wait for terminal truth:
   - run state becomes `completed`
   - active run no longer has pending rows for that run
   - first-check/screening outputs reconcile to processed rows
11. Restore or confirm ownership state.

## Parked Condition
Status:
- staged proof complete
- live loop verification not run
- live handoff parked because F061 is busy

Resume trigger:
- F061 run state is idle or the user explicitly approves a safe switch after the current stocklist run is stopped at a boundary.
