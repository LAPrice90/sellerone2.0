# F Single Login System Rebuild Review

Reviewed UTC: 2026-06-09T10:32:56Z
Reviewer role: SellerOne F Reviewer
Job: `F-SINGLE-LOGIN-SYSTEM-REBUILD`
Packet: `tasks/approved/MGR_F_SINGLE_LOGIN_SYSTEM_REBUILD.md`
Worker result: `CONTROL/F_SINGLE_LOGIN_SYSTEM_REBUILD_RESULT.md`
State dashboard: `CONTROL/F_SINGLE_LOGIN_SYSTEM_STATE_DASHBOARD.md`

## Reviewer Result

PASS - code-level rebuild gates are satisfied, isolated verification passed, and live Seller Central proof remains correctly blocked.

This review does not prove a live Seller Central login. It proves the safer pre-live shape: one controller-owned request path, duplicate login attempts frozen before Seller Central click, a redacted state dashboard, logged-out continuation behavior, and UI human-assist routing through the controller.

## Gate Review

| Gate | Reviewer result | Evidence |
|---|---|---|
| 1 - Containment audit | PASS | `CONTROL/F_SINGLE_LOGIN_SYSTEM_STATE_DASHBOARD.md` maps the UI login button, FPM130 child launch, F061 scanner Chrome route, old BBP auto-login, Seller Central auto-login, and recovery route. |
| 2 - Login attempt freeze | PASS | Focused tests passed, and fresh F MOT shows Seller Central auth state `normal_scan_only` with latest proof disabled instead of attempted live login. |
| 3 - Redacted state dashboard | PASS | `CONTROL/F_SINGLE_LOGIN_SYSTEM_STATE_DASHBOARD.md` exists and shows Dashboard Yes/No, login mode, browser owner, freeze state, held/second-check state, and next safe action without secrets. |
| 4 - Logged-out continuation test | PASS | Focused F061 tests prove normal pending rows continue before login-backtrack rows, login-only rows are not retried without a request, and login mode drains backtrack rows first. |
| 5 - Human-assist path through controller | PASS | UI helper writes `f061_login_mode.requested` through `write_login_controller_request` with `controller_owner=F_LOGIN_CONTROLLER_REWRITE_V1`; targeted UI test passed. |
| 6 - Live proof readiness | PASS AS BLOCKED | Worker correctly left live proof blocked pending Reviewer/Operations approval and a separate proof boundary. |

## Boundary Review

Implementation changes are inside the approved F/O code boundary described by the packet:

- F controller helper: `scripts/flows/F/login_controller.py`
- FPM130 request reading/reactivation: `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- F scanner handoff/freeze: `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- O operator UI request routing only: `scripts/flows/O/O400_operator_ui.py`
- focused tests under `tests/`

No reviewed evidence shows widening into A, B, E, H, or O business actions beyond the allowed O UI request route.

## Verification Run

- `python -m py_compile scripts/flows/F/login_controller.py scripts/flows/F/legacy_scanner_2_1/Webscrape.py scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py scripts/flows/O/O400_operator_ui.py` - passed.
- `python -m pytest tests/test_f_legacy_webscrape_money_input.py -k "bbp_dashboard_login_handoff" -q` - 5 passed, 49 deselected.
- `python -m pytest tests/test_f061_run_legacy_first_checks_local.py -k "normal_mode_processes_pending_before_login_backtrack or normal_mode_does_not_retry_only_login_rows_without_request or login_mode_selects_login_backtrack_first" -q` - 3 passed, 65 deselected.
- `python -m pytest tests/test_f_login_controller.py tests/test_fpm130_live_cycle.py tests/test_f_legacy_webscrape_money_input.py tests/test_f061_run_legacy_first_checks_local.py -k "seller_central or email_continue or login_mode or login_controller or visible or background_browser_mode or normal_mode_processes_pending_before_login_backtrack or normal_mode_does_not_retry_only_login_rows_without_request" -vv` - 82 passed, 132 deselected.
- `python -m pytest tests/test_o_ui_operator_view.py::test_price_list_login_mode_request_writes_control_file_and_event_only -q` - 1 passed.
- `python -m sellerone_manager.app --hourly-mot --mot-flow F` - status `decision_needed`, fail_count `1`, warn_count `3`.

## MOT Truth Review

The read-only F MOT is truthful for this packet.

Remaining F fail:

- `f_rescan_priority_proof`: `parked_timeout=170`

Reviewer classification: outside this login rebuild. It is a protected F rescan decision about parked RESCAN rows, not proof that the single-login controller rebuild failed.

Relevant F login warnings remain visible and are not hidden:

- `f_login_mode_state`: `still_required`
- `f_seller_central_eligibility_auth_state`: `normal_scan_only`
- `f_bbp_iframe_plugin_state`: `stderr_blocked`

These warnings support the decision to keep live proof blocked until a separate approved proof boundary exists.

## Forbidden Action Check

No reviewer evidence shows any of the following were performed by the worker or this review:

- live Seller Central login
- SMS/code or phone request
- Amazon security bypass
- MFA disablement
- browser/profile/cookie mutation
- separate Chrome workaround
- F runtime pause or restart
- Task Scheduler change
- price, Sheet, database, purchase, receiving, send-to-Amazon, output deletion, or cleanup apply
- queue edit beyond this review note

## Final Reviewer Position

PASS.

Operations can treat `F-SINGLE-LOGIN-SYSTEM-REBUILD` as pre-live gate-passed. The next step is not live login by default. The next step is a separate Operations-approved live proof readiness packet if Operations wants to move from blocked readiness to a controlled proof window.
