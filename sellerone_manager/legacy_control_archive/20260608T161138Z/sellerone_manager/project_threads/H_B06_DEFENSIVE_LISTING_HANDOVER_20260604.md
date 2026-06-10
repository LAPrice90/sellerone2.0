# H B06 Defensive Listing Handover - 2026-06-04

## Why This Exists
This work was started from the F manager lane by mistake. H now needs to own the safety proof and any next repair.

## Current B06 State
- SKU: `6V-EEC1-2S9Z`
- ASIN: `B06WW79DX5`
- Config: `config/h_defensive_listing_protection.csv`
- Current config state: `live_write_enabled=1` for B06 only.
- Backup before activation: `config/backups/h_defensive_listing_protection_before_live_activation_20260604.csv`

## Intended Strategy
- If a rival is strictly below us, B06 defensive mode may undercut by 1p inside SellerOne floor and ceiling.
- If the rival is gone, equal, or above us, defensive mode must stand down.
- Normal H repricing then controls recovery toward the normal max/ceiling.
- There should be no 24h rival-absence wait, no slow recovery ladder, and no separate recovery repricer.

## Code State Already Applied
- Defensive helper: `scripts/phase1/phase1_defensive_listing.py`
- H decision hook: `scripts/phase1/phase1_main_loop.py`
- Proof storage: `scripts/phase1/phase1_storage.py`
- MOT visibility: `sellerone_manager/hourly_mot.py`
- Focused tests passed from the accidental F-lane work:
  - `python -m pytest tests/test_phase1_defensive_listing.py tests/test_phase1_main_loop.py tests/manager/test_h_hourly_mot.py -q`
  - result: `77 passed`

## Current Live Proof State
- Live B06 proof is not yet confirmed.
- `out/h_defensive_listing_action_log.csv` was missing at last check.
- Read-only H MOT after the simplification showed:
  - `fail_count=5`
  - `warn_count=3`
  - defensive listing row: live-enabled but waiting for proof
- Latest completed failed H run:
  - `H_20260604T101005Z`
  - failure marker: `CHILD_RC_NONZERO / atexit_without_success_marker`
- A newer H run was observed running:
  - `20260604T104846Z`
  - because it started before the simplification, clean proof needs the next normal H code-load/run boundary or a manager-approved H proof window.

## Manager Task Packets To Use
- `sellerone_manager/tasks/approved/MGR_H_repair_h_defensive_listing_stand_down_guard.md`
- `sellerone_manager/tasks/approved/MGR_H_repair_h_defensive_listing_mot_proof_visibility.md`
- If H is still failing before B06 proof, use the H runtime/finalizer packets instead of treating this as an F issue.

## H Next Safe Job
1. Read H manager state and the approved H packets.
2. Check current H owner/run state without restarting anything.
3. Run read-only H MOT.
4. Check:
   - `out/h_defensive_listing_action_log.csv`
   - `out/h_defensive_listing_daily.csv`
   - `out/systems/M/hourly_mot_H.csv`
5. Confirm whether B06 proof shows one of:
   - defensive action inside floor/ceiling, or
   - defensive not triggered and normal H control.
6. If no proof exists because H failed first, package/repair the H runtime/finalizer issue in the H lane.

## Boundaries
- Do not run H manually without an approved proof window.
- Do not restart workers.
- Do not pause or resume scheduler ownership.
- Do not publish.
- Do not change prices directly.
- Do not edit queues.
- Do not write Google Sheets.
- Do not align local DB data.
- Do not delete outputs.
- Do not widen back into F.

