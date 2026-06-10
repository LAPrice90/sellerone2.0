# F Single Login System Rebuild Result

Updated UTC: 2026-06-09T10:30:00Z
Job: `F-SINGLE-LOGIN-SYSTEM-REBUILD`
Worker result: code fix applied, isolated verification passed, live proof readiness blocked.

## Summary

F login routing is now more contained around the existing login controller.

The UI login button and FPM130 request handling use controller request helpers. The old scanner Seller Central handoff now checks the controller attempt control before clicking the BBP Seller Central login control, so normal-scan-only mode freezes live Seller Central login before a new tab or credential/code path starts.

## Gate Results

| Gate | Result | Evidence |
|---|---|---|
| 1 - Containment audit | Passed for mapped code paths | Entry point map written in `CONTROL/F_SINGLE_LOGIN_SYSTEM_STATE_DASHBOARD.md`. |
| 2 - Login attempt freeze | Passed for code-level freeze | New pre-click freeze test passed; latest live Seller Central proof rows show `disabled / normal_scan_only` and `attempted_flag=0`. |
| 3 - Single state dashboard | Passed | `CONTROL/F_SINGLE_LOGIN_SYSTEM_STATE_DASHBOARD.md` created. |
| 4 - Logged-out continuation test | Passed at focused row-flow level | Tests prove normal rows continue while login-backtrack rows are held, and login-only rows are not retried without a request. |
| 5 - Human-assist path | Passed at request-routing level | UI writes `f061_login_mode.requested` through controller helper and does not open Chrome. |
| 6 - Live proof readiness | Blocked | Live Seller Central proof is not allowed until Reviewer/Operations confirms all gates and a separate approved proof boundary. |

## Implementation Changes

- Added controller request helpers in `scripts/flows/F/login_controller.py`.
- Routed FPM130 login-mode request reads and reactivation writes through the controller helper in `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`.
- Routed the operator UI login button through the controller helper in `scripts/flows/O/O400_operator_ui.py`.
- Added a pre-click Seller Central freeze in `scripts/flows/F/legacy_scanner_2_1/Webscrape.py` so frozen mode returns `normal_scan_only` before the BBP Seller Central login control is clicked.
- Added focused tests for controller-owned request files, UI request ownership, pre-click freeze, and logged-out continuation behavior.

## Focused Tests Run

- `python -m py_compile scripts/flows/F/login_controller.py scripts/flows/F/legacy_scanner_2_1/Webscrape.py scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py scripts/flows/O/O400_operator_ui.py` - passed.
- `python -m pytest tests/test_f_legacy_webscrape_money_input.py -k "bbp_dashboard_login_handoff" -q` - 5 passed.
- `python -m pytest tests/test_f061_run_legacy_first_checks_local.py -k "normal_mode_processes_pending_before_login_backtrack or normal_mode_does_not_retry_only_login_rows_without_request or login_mode_selects_login_backtrack_first" -q` - 3 passed.
- `python -m pytest tests/test_f_login_controller.py tests/test_fpm130_live_cycle.py tests/test_f_legacy_webscrape_money_input.py tests/test_f061_run_legacy_first_checks_local.py -k "seller_central or email_continue or login_mode or login_controller or visible or background_browser_mode or normal_mode_processes_pending_before_login_backtrack or normal_mode_does_not_retry_only_login_rows_without_request" -vv` - 82 passed, 132 deselected.

## Read-Only F MOT

Latest read-only F MOT before this result update:

- Command: `python -m sellerone_manager.app --hourly-mot --mot-flow F`
- Status: `decision_needed`
- Fails: 1
- Warnings: 4
- Not checked: 1
- Remaining fail: `f_rescan_priority_proof` with `parked_timeout=170`, which is a protected F rescan decision and not part of this login rebuild.
- Relevant login warnings: `f_login_mode_state=holding`, `f_seller_central_eligibility_auth_state=normal_scan_only`.

## Remaining Blocker

Live Seller Central proof readiness is blocked.

Reason: the risk gates are code-tested and documented, but live proof still requires Operations/Reviewer confirmation and an approved proof boundary. This worker did not start live login, SMS/code, phone, browser/profile/cookie mutation, separate Chrome workaround, F runtime pause/restart, or Amazon security action.

## Next Safe Step

Reviewer should retest this packet from fresh context, then Operations can decide whether a separate live proof readiness packet is safe.
