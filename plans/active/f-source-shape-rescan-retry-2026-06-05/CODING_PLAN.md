# F Source-Shape Rescan Retry Fix

- Current phase: monitored validation
- Changed at UTC: 2026-06-05T06:47:41Z
- Goal: stop blank rescan-retry rows from blocking the live F owner and stop future recovery previews from requeueing source rows that are not scan-ready

## Allowed Files

- `scripts/flows/F/price_list_manager/FPM122_preview_f061_rescan_recovery.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`

## Isolated Proof

- `python -m py_compile scripts/flows/F/price_list_manager/FPM122_preview_f061_rescan_recovery.py scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `python scripts/flows/F/price_list_manager/FPM122_preview_f061_rescan_recovery.py`
- Direct function proof:
- `_looks_scan_ready` returns `False, source_row_missing_supplier_title` for DHB row key `9639381947e967ce6636787a0e82b723e39a1acc`
- `_active_f061_state` now selects `td_synnex`
- `_active_pending_rows_for_supplier_run(... dhb ...)` now returns `0`
- `_active_rescan_pending_rows_for_supplier_run(... dhb ...)` still returns `3`

## Live Monitoring Target

- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/price_list_manager/live/fpm_live_supervisor_state.txt`

## Poll Cadence

- First check at `+5 minutes`
- Second check at `+10 minutes`
- Then every `+15 minutes`
- Stop at `+60 minutes` if no fresh-owner or fresh-cycle evidence loads the patch

## Success Threshold

- A fresh F owner or fresh cycle writes status after the code change
- `state` is no longer `blocked_source_shape_guard` for DHB parked rescan rows
- DHB parked retry rows remain non-runnable unless a scan-ready source row exists
- No new F live FAIL appears from this fix path

## Timeout Rule

- If no fresh runtime evidence appears by `+60 minutes`, mark this work parked pending next F proof window
- If a fresh owner still reports `blocked_source_shape_guard` on a parked rescan row, inspect the latest active row and recovery preview pair before any queue edit

## Automatic Next Step

- When fresh runtime evidence exists, re-read the three live artifacts and either close this as proven or record the exact remaining blocker

## 2026-06-05T08:41Z Correction

- Finding: DHB conversion already holds blank-cost rows correctly. `GCT019` from `Trade Price May 2026.xlsx` has blank `Trade Price`, and the converted `batch_rows.csv` row is `scan_eligibility=hold` with `eligibility_reason=missing_or_invalid_cost`.
- Real fault: RESCAN recovery/preview could treat an already-active row as clean before checking that the active/source row still had a positive unit cost.
- Code guard added:
- `FPM122_preview_f061_rescan_recovery.py` now reports already-active rows with missing cost as blocked evidence instead of clean already-active evidence.
- `FPM123_apply_f061_rescan_recovery.py` now refuses to write a stale preview into active scanner rows when the proposed active row is missing title or unit cost.
- Isolated proof: `python -m pytest tests/test_dhb_supplier_converter.py tests/test_fpm122_preview_f061_rescan_recovery.py tests/test_fpm123_apply_f061_rescan_recovery.py` passed with 5 tests.
- Read-only preview proof: refreshed `f061_rescan_recovery_preview.csv`; `GCT019` now shows `proposed_action=already_active`, `eligible_apply_flag=0`, and `block_reason=already_active_source_row_missing_unit_cost`.
- Manager proof: `python -m sellerone_manager.app --hourly-mot --mot-flow F` still reports `decision_needed`, because the live queue still contains the protected already-active bad row and cannot be edited from this manager fix.

## 2026-06-05T08:51Z Protected No-Price Active Row Recovery

- User-approved protected action: remove active scanner listings with no pricing.
- Backup created: `out/systems/F/price_list_manager/queue_safety_backups/remove_no_price_20260605T085025Z`
- Row removed from active scanner path: DHB `GCT019`, barcode `10386040004367`, row key `9639381947e967ce6636787a0e82b723e39a1acc`.
- Files updated:
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
- `out/systems/F/inbox/suppliers/dhb/active_run.csv`
- `out/systems/F/inbox/supplier_price_list_run_state.csv`
- `out/systems/F/inbox/suppliers/dhb/run_state.csv`
- `out/systems/F/live/f_screening_row_state_live.csv`
- Proof written: `out/systems/F/price_list_manager/test_mode/f061_no_price_active_row_recovery.csv`
- Result: active scanner rows with blank/non-positive/invalid `unit_cost` now equal `0`; DHB active RESCAN rows now equal `2`, both with costs.
- Fresh preview result: `preview_rows=179`, `requeue_rows=12`, `retry_exhausted_rows=75`, `source_blocked_rows=2`, `already_active_rows=90`, `blocked_rows=90`.
- Live owner retest: pending. Latest `live_cycle_status.csv` still shows the older `blocked_source_shape_guard` row from before the edit.
- Next trigger: wait for a fresh `live_cycle_status.csv` row after `2026-06-05T08:51:13Z`.
- Success condition: F live owner no longer reports `blocked_source_shape_guard` for DHB `GCT019`, and no active scanner rows have missing/invalid unit cost.
- If it fails: do not restart F061 automatically; inspect whether the owner is stale/stuck and create a separate F owner-resume proof packet if needed.

## 2026-06-05T09:12Z Visible Login Loop Evidence

- New live evidence after no-price row recovery: F owner moved from the DHB no-price blocker into `running`.
- Latest live state: `state=running`, `active_supplier_id=dhb`, `active_f061_run_id=fpm_dhb_20260506T212446Z`, `last_action=resume_f061_active_run`, `last_action_status=scanner_running`.
- Current disruption: F061 child repeatedly reports browser visibility events with `seller_central_eligibility_login_still_required`.
- Operator impact: Chrome is repeatedly pulled visible/missing/visible, which makes the PC hard to use.
- Root-cause classification: not a source price file issue. This is the Seller Central eligibility login gate and visible browser attention loop.
- Required fix direction: F should park once with a clear `waiting_for_seller_central_login` state instead of repeatedly forcing visibility. A separate F visible-login-control task packet is needed before changing that worker behaviour.
- Do not solve by opening a separate Chrome window, restarting F061, or forcing broad worker visibility.

## 2026-06-05T09:51Z Visible Login Control Repair Applied

- User approval: approved `F-VISIBLE-LOGIN-CONTROL` repair in chat.
- Code changed:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- Behaviour changed:
- Seller Central login can surface the scanner-owned browser once.
- After the first prompt, F writes `seller_central_eligibility_login_waiting_parked` and keeps the next child minimized instead of flashing Chrome repeatedly.
- The Seller Central visibility marker is no longer cleared just because a new login-mode child starts.
- Default BBP/plugin profile is now `C:\Users\Luke\AppData\Local\Chrome_UC136v2` with `BBPProfile1`.
- Live mitigation applied without restart:
- Backed up current live visibility controls to `out/systems/F/price_list_manager/queue_safety_backups/visible_login_pause_20260605T095110Z`.
- Wrote `f061_login_mode.requested` with `status=canceled` and `reason=user_pc_unusable_visibility_loop_paused`.
- Wrote `f061_browser_visibility_state.txt` as hidden with Seller Central login still required.
- Wrote `f061_seller_central_window_shown.marker` so patched future logic parks instead of re-showing.
- Proof:
- `python -m pytest tests/test_fpm130_live_cycle.py -k "seller_central or login_mode or default_bbp_profile or visible_signal" tests/test_f061_run_legacy_first_checks_local.py -k "login or profile or auth"` passed with 56 selected tests.
- `python -m py_compile scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py scripts/flows/F/F061_run_legacy_first_checks_local.py` passed.
- Short live poll after the pause showed latest browser visibility event as `hidden/auth_confirmed` at `2026-06-05T09:51:12Z`, not another visible loop.
- Remaining truth: Seller Central eligibility login itself is still not fully proved. The repair stops the repeated screen flashing and makes the state manageable.
