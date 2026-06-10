# F Repair Ready For Bounded Proof Result - 2026-06-09

Job: F-SELLER-CENTRAL-SAFE-LOGIN-TODAY
Role: SellerOne F Worker
Mode: repair-only, no live proof run

## Starting Blocker

- Previous live window closed with FPM130/F061 showing `login_mode=1`, but the Seller Central controller still reported `normal_scan_only` / `attempt_mode_not_enabled`.
- Dashboard Yes/No was not proved.
- Logged-out continuation was not proved because TD Synnex remained first and no held-for-second-check return path was recorded.

## Repair Applied

- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - F061 login-mode handoff now also passes `SELLER_CENTRAL_LOGIN_ATTEMPT_MODE=1` into the scanner-owned child when the single login controller has an active bounded request.
  - Stale Seller Central attempt-mode environment is removed when there is no active request, preventing old approval state from leaking into normal scanning.
  - Added logged-out continuation parking: if a bounded login-mode chunk returns `still_required` without Dashboard proof, login-required supplier rows are marked `second_check_after_login`, the current supplier run is marked `held_for_login`, and the next safe active supplier becomes the active return path.
  - Added a `seller_central_second_check_hold` live-cycle event so the held supplier/run and next supplier/run are recorded.

- `tests/test_fpm130_live_cycle.py`
  - Added/updated focused checks for Seller Central attempt-mode handoff.
  - Added stale attempt-mode cleanup coverage.
  - Added TD Synnex held-for-second-check continuation coverage.

## Local Tests

- Passed: `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py`
- Passed: `python -m pytest tests\test_fpm130_live_cycle.py -k "login_mode_request_forces_visible_child_env or clears_stale_login_mode_env_without_request or still_required_login_request_stays_active or holds_td_synnex_for_second_check" -q`
  - Result: 4 passed, 84 deselected
- Passed: `python -m pytest tests\test_f_login_controller.py tests\test_f_seller_central_login_recovery.py -q`
  - Result: 16 passed

## Boundary Confirmation

- No live F proof run was started.
- No normal F business scanning was restarted.
- No second F owner was created.
- No Task Scheduler change was made.
- No Amazon security bypass, MFA change, repeated SMS/phone/code attempt, separate Chrome workaround, secret exposure, price change, Sheet write, DB alignment, output deletion, purchase, receiving, send-to-Amazon, or A/B/E/H/O widening occurred.

## Result

Repair ready for a new bounded F proof window.

The next bounded proof should prove one of:

- Dashboard Yes/No through the single controller, or
- logged-out continuation where TD Synnex is held for Seller Central second-check and the next safe price file moves with return path recorded.
