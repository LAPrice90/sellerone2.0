# Execution Batch 001 - Complete For Guard

## Purpose
Stabilize source truth before any stock-decider implementation.

## Approval Status
Approved by user message: `approve`.

## Completed Work
- Added a guarded F source-shape check for TD Synnex rows.
- Wired the guard into FPM staging, FPM staged apply, and FPM live active-run resume.
- Confirmed live F was still pointed at old shifted-column TD Synnex run `fpm_td_synnex_20260519T090704Z`.
- Drained and reloaded the F owner through the F-owned boundary.
- Proved the restarted F owner blocks the bad active run before scanner launch.
- Added a loop sleep rule so blocked states do not spin continuously.
- Reloaded the F owner again so the live owner uses the one-minute blocked-state sleep floor.

## Remaining Parked Decision
- Decide whether to quarantine/replace the current 43,039-row bad TD Synnex active run.
- If approved, take a live backup first, then replace only through a guarded F boundary.
- This is parked as a separate live F queue-state decision, not part of the O cost bridge implementation.

## Files Expected To Touch After Approval
- `scripts/flows/F/price_list_manager/FPM070_stage_f061_handoff.py`
- `scripts/flows/F/price_list_manager/FPM100_apply_f061_handoff.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- targeted FPM tests
- this plan folder

## Not Allowed
- No Google Sheets writes.
- No local DB alignment changes.
- No second F owner.
- No mid-chunk kill.
- No O restock recommendation changes in this batch.

## Proof Required
- Tests pass: completed, 76 targeted FPM tests passed.
- F active owner remains single-owner: completed, PID `6584`.
- Current active owner after final reload: PID `35404`.
- Bad shifted active-run rows are not allowed to feed O cost truth: completed by live `blocked_source_shape_guard`.
- Active TD Synnex rows have real SKU, title, cost, and barcode fields: not complete because the bad active run has not been replaced yet.

## Latest Live Proof
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` at `2026-05-19T11:58:50Z`:
  - `state=blocked_source_shape_guard`
  - `active_supplier_id=td_synnex`
  - `active_f061_run_id=fpm_td_synnex_20260519T090704Z`
  - `pending_rows=43039`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv` recorded `source_shape_guard_blocked` with `td_synnex_supplier_title_numeric_like`.
- After the blocked-state sleep change, `out/systems/F/price_list_manager/live/live_cycle_status.csv` at `2026-05-19T12:03:36Z` still shows `blocked_source_shape_guard` under PID `35404`.
- Proof snapshot: `plans/active/repricing-stock-cost-bridge-2026-05-19/proof/phase1_source_shape_guard_final_20260519T120528Z`.
