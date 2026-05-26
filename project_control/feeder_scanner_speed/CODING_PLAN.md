# Feeder Scanner Speed - Coding Plan

Created UTC: 2026-05-01T10:00:00Z

## Current Phase
Phase 4 - UI-controlled Login Mode proof and automatic visible-browser suppression.

## Scope
Keep BBP/Amazon login recovery inside the normal script-owned F061 browser, but only show that browser when the operator activates Login Mode from the Price List Queue UI.

Do not change:
- scanner chunk size
- API rate limits
- supplier handoff rows
- Google Sheets

## Allowed Files
- `scripts/flows/F/_scanner_state.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- focused F tests
- `project_control/F_SCANNER_SPEED_PRODUCTION_PLAN.md`
- this coding plan

## Target Outputs
- `out/systems/F/live/f_scanner_speed_ledger_live.csv`
- health rows in existing F health output for speed evidence and bottleneck warnings
- `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`

## Tests
- schema/contract test for the new output
- F061 focused test proving ledger rows are written
- F061 focused test proving no scanner behavior changes are needed for zero-row runs
- FPM130 focused test proving auth-attention overrides a stale hidden/logged-in browser state
- FPM130 focused test proving blocked chunks save `LOGIN_REQUIRED` state for the next child

## Isolated Proof
Run focused pytest for FPM130/F061 scanner behavior.

## Live Proof
Confirmed on 2026-05-01T09:17:52Z.

Evidence:
- `out/systems/F/live/f_scanner_speed_ledger_live.csv` wrote 5 Entertainment Trading rows.
- `feeder_legacy_sheet_health.csv` wrote `f_scanner_speed_ledger_runtime=ok`.
- `feeder_legacy_sheet_health.csv` wrote `f_scanner_speed_bottleneck_runtime=ok`.
- No scanner chunk size, API interval, browser retry, queue priority, or handoff setting was changed.

## Monitoring Target
After deployment, check:
- `out/systems/F/live/f_scanner_speed_ledger_live.csv`
- `out/systems/F/live/feeder_legacy_sheet_health.csv`
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`

## Success Threshold
- focused tests pass
- when BBP login-required evidence appears outside active Login Mode, affected rows are parked and the next child stays `browser_mode=minimized`
- when the operator presses Login, the next normal F061 child starts with `browser_mode=visible` and `F061_LOGIN_MODE=1`
- login-backtrack rows remain pending for later merge/backdating instead of being falsely completed
- no chunk size, API interval, or Google Sheets setting changes

## Timeout Rule
If live scanner evidence is not available in the current turn, mark live proof as not yet proven and keep the FPM owner on the normal F061 path. Do not use the F-only visible-login maintenance path unless the user explicitly asks for that separate maintenance tool.

## Automatic Next Step
Keep FPM on the normal script-owned F061 scanner path. When login-required evidence appears, rows must be parked under the UI Login count. Only an active UI Login Mode request should make the next normal child visible. Do not use a separate standalone Chrome login window unless the user explicitly asks for one.

## Current Live Follow-Up
Recorded UTC: 2026-05-09T10:42:30Z

Trigger:
- User login in the visible normal F061 child.
- Scanner owner reload after applying the scanner-state and BBP profile fixes.

Artifact to inspect:
- `out/systems/F/price_list_manager/live/live_cycle_status.csv`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`

Current state:
- FPM live scanner was restored from the mistaken separate-browser login path.
- F-only visible-login request is cleared.
- FPM state is `running`.
- Current normal F061 child started with `browser_mode=visible`, but the old already-loaded owner hid it again after `BBP login skipped: already authenticated`.
- Code fix changed `scripts/flows/F/_scanner_state.py` so `Dashboard yes/no ignored non yes/no value => LOGIN` is treated as `LOGIN_REQUIRED` even if an earlier log line says already authenticated.
- The visible Windows launcher/startup forcing attempted at 2026-05-09T10:16Z was rolled back because it exposed the wrong Chrome profile.
- Profile inspection found the BuyBotPro extension under `C:\Users\Luke\AppData\Local\Chrome_UC136v2\BBPProfile1` and `BBPProfile2`; the normal scanner had been using `Chrome_UC136\BBPProfile`, which did not contain the BuyBotPro extension.
- Code fix changed `scripts/flows/F/F061_run_legacy_first_checks_local.py` so the BBP-side Chrome defaults to `Chrome_UC136v2` / `BBPProfile1`.
- Code fix added a preflight check for the BuyBotPro extension manifest. If the profile does not contain BuyBotPro, F061 reports login/profile attention instead of silently burning rows through `No BBP iframe`.
- Code fix changed specialist Chrome cleanup so normal scanner startup preserves the profile session by default; force cleanup is used only after a real driver launch failure.
- Focused tests passed: `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_f_scanner_state.py tests\test_fpm130_live_cycle.py -q` -> `69 passed`.
- Active supplier is `stax`, run `fpm_stax_20260507T151124Z`, pending rows `22778`.
- The user must log in through the next script-owned F061 browser window, not a separate Chrome window.

Success condition:
- After the scanner owner reloads, FPM keeps ordinary logged-out scanning hidden/minimized unless `f061_login_mode.requested` is active.
- The next Login Mode F061 child uses the BBP plugin profile (`Chrome_UC136v2` / `BBPProfile1`) when the operator presses Login.
- Normal F061 startup does not force-stop specialist Chrome unless recovery from a launch failure is needed.
- After the user logs in inside that script-owned browser, the scanner records clean login evidence or Stax pending rows decrease below `22778`.

If the condition fails:
- Do not open a separate standalone login window.
- Do not force the next normal F061 child visible without a UI Login Mode request.
- Inspect the newest `f061_child_stdout.log`, `f061_child_stderr.log`, `feeder_legacy_scrape_evidence_live.csv`, and `f_login_backtrack_evidence_live.csv`.
- Do not mark live verification complete until Stax pending rows move or the affected rows are safely parked without blocking the main queue.

## Current Live Follow-Up - Manual Login Hold
Recorded UTC: 2026-05-09T10:52:30Z

Trigger:
- The visible normal F061 child detects a BBP login form.

Artifact to inspect:
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- `out/systems/F/price_list_manager/live/f061_child_stderr.log`
- `out/systems/F/price_list_manager/live/f061_child_stdout.log`

Current state:
- Evidence shows the scanner was not cleanly logged in now.
- Old child behavior kept logging `Submitted BBP login` and then `BuyBotPro checks` errors, so the browser flashed up and closed after the chunk.
- Code fix changed `scripts/flows/F/legacy_scanner_2_1/Webscrape.py` so visible F061 login no longer auto-submits and closes immediately.
- Focused tests passed: `python -m pytest tests\test_f_legacy_webscrape_money_input.py tests\test_f061_run_legacy_first_checks_local.py tests\test_f_scanner_state.py tests\test_fpm130_live_cycle.py -q` -> `84 passed`.
- Live patched child started as `pid=20152`, `browser_mode=visible`, `started=2026-05-09T10:51:14Z`.
- Live patched child logged: `BBP manual login required; keeping the visible scanner browser open for up to 900 seconds.`

Success condition:
- User logs in inside the script-owned F061 Chrome window before the 900 second hold expires.
- After login, F061 logs `BBP manual login completed` or records clean BBP fields instead of `BBP_LOGIN_REQUIRED`.
- Stax pending rows continue below `22734`.

If the condition fails:
- Do not open a separate standalone Chrome login window.
- Keep the normal F061 child visible and extend the login hold if 900 seconds is not enough.
- Inspect `f061_child_stderr.log` for whether the hold timed out, completed, or still sees BBP login form.

## Login Mode Phase 1 - UI Control
Recorded UTC: 2026-05-09T11:20:00Z

Scope:
- Add the Price List Queue UI operator control for login recovery.
- Do not make FPM130 consume the request yet.
- Do not launch Chrome from the UI.
- Do not change Google Sheets.

Changed files:
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_o_ui_operator_view.py`
- `project_control/F_PRICE_LIST_SCANNER_LOGIN_MODE_DESIGN.md`

Implemented:
- Active scanner card now has `LOGIN` between `FAIL` and `RE SCAN`.
- Active supplier row overlay now has a `LOGIN` count between `FAIL` and `Rescan`.
- UI reads login count from `supplier_price_list_active_run.csv` rows with `login_backtrack_pending`, `login_backtrack_running`, or `completion_block_reason=bbp_login_required`.
- UI reads auth state from `f061_browser_visibility_state.txt`.
- UI writes `out/systems/F/price_list_manager/live/f061_login_mode.requested` when Login is pressed.
- UI appends `login_mode_requested` to `live_cycle_events.csv`.
- UI explicitly does not write `f061_visible_login.requested`.

Proof:
- `python -m py_compile scripts\flows\O\O400_operator_ui.py` passed.
- `python -m pytest tests\test_o_ui_operator_view.py -q` -> `63 passed`.

Next implementation phase:
- Phase 2 - FPM130 must consume `f061_login_mode.requested` at the next normal child boundary and pass login-mode environment flags to F061.

Success condition for Phase 2:
- Pressing Login in the UI causes the next normal F061 child, not a separate Chrome window, to start visible with login-mode env flags.

## Login Mode Phase 2 - FPM130 Request Consumption
Recorded UTC: 2026-05-09T11:17:20Z

Scope:
- Make FPM130 consume `f061_login_mode.requested` at the next normal scanner child boundary.
- Do not open Chrome directly from FPM130 or the UI.
- Do not write `f061_visible_login.requested`.
- Do not change Google Sheets.

Changed files:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_fpm130_live_cycle.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- this coding plan

Implemented:
- FPM130 reads `out/systems/F/price_list_manager/live/f061_login_mode.requested`.
- An active login-mode request forces the next normal F061 child to `F061_BACKGROUND_BROWSER_MODE=visible`.
- The child environment now receives:
  - `F061_SHOW_WINDOWS=1`
  - `FPM_LIVE_HIDE_SCRAPER_WINDOWS=0`
  - `F061_LOGIN_MODE=1`
  - `F061_LOGIN_HOLD_SECONDS=<request hold_seconds, default 60>`
  - `F061_LOGIN_MODE_REQUEST_PATH=<request file>`
  - `F061_MANUAL_BBP_LOGIN_WAIT_SECONDS=<same hold seconds>` for compatibility with the current visible manual-login hold.
- If no active login request exists, stale inherited login-mode environment variables are removed from the child env.
- FPM130 writes `login_mode_child_started` to `live_cycle_events.csv` when a request is consumed at a child boundary.
- FPM130 writes `f061_login_mode_request_state` to `live_cycle_health.csv`; it is `ok` while a requested child is starting and `warn` when a request exists but no child can start.

Proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py -q` -> `28 passed`.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_o_ui_operator_view.py -q` -> `91 passed`.
- Pytest printed the existing Windows temp `pytest-current` cleanup PermissionError after tests completed; tests themselves passed.

Verification status:
- Code fix applied.
- Isolated verification passed.
- Live loop verification not yet proven.

Next implementation phase:
- Phase 3 - F061 must use `F061_LOGIN_MODE=1` to pick the first BBP-login-required backtrack row, open that ASIN in the normal script-owned browser, hold/recheck for login, and replay the login backlog before returning to normal rows.

Live proof trigger:
- Existing live or test active run has at least one `login_backtrack_pending` row with `completion_block_reason=bbp_login_required`.
- Operator presses Login in the Price List Queue UI.

Live proof artifacts:
- `out/systems/F/price_list_manager/live/f061_login_mode.requested`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/price_list_manager/live/live_cycle_health.csv`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- `out/systems/F/price_list_manager/live/f061_child_stdout.log`
- `out/systems/F/price_list_manager/live/f061_child_stderr.log`

Live success condition:
- `live_cycle_events.csv` contains `login_mode_child_started`.
- The matching child status/logs show `browser_mode=visible`.
- The child environment is the normal F061 path, not `FPM160_f061_visible_login_maintenance.py open`.
- No `f061_visible_login.requested` is created by this mode.

If the condition fails:
- Do not open a separate standalone Chrome login window.
- Inspect FPM130 child-env decision and newest F061 child logs.
- Restore the request file if needed and retry only through the normal F061 child boundary.

## Login Mode Phase 3 - F061 Login-Backtrack Runtime
Recorded UTC: 2026-05-09T11:26:06Z

Scope:
- Make F061 use `F061_LOGIN_MODE=1` to decide when parked login rows should run.
- Let normal mode keep processing ordinary pending rows without repeatedly retrying login-backtrack rows.
- Keep all browser login inside the normal script-owned F061 browser.
- Do not change Google Sheets.

Changed files:
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `tests/test_o_ui_operator_view.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f_legacy_webscrape_money_input.py`
- this coding plan

Implemented:
- F061 now reads:
  - `F061_LOGIN_MODE`
  - `F061_LOGIN_HOLD_SECONDS`
  - `F061_LOGIN_MODE_REQUEST_PATH`
- In normal mode, if ordinary `pending` rows exist, F061 processes those first and leaves `login_backtrack_pending` rows parked.
- In normal mode, if only login-backtrack rows remain, F061 does not retry them without a login-mode request; it returns quickly with the backlog still pending.
- In Login Mode, F061 prioritizes login-backtrack rows before ordinary pending rows.
- F061 writes `login_mode_hold_started`, `login_mode_authenticated`, `login_mode_still_required`, and `login_mode_backlog_drained` events to `live_cycle_events.csv` where applicable.
- F061 updates `f061_login_mode.requested` status:
  - `holding` while selected login rows are being opened
  - `still_required` if login is still blocked
  - `authenticated_backlog_remaining` if login succeeded but backlog remains
  - `drained` when login backlog reaches 0
- F061 writes `f061_login_mode_runtime` to `feeder_legacy_sheet_health.csv`.
- Webscrape now refreshes/rechecks once after the visible manual-login hold expires before returning `BBP_LOGIN_REQUIRED`.
- The UI now treats a request file with `status=still_required`, `drained`, `consumed`, `completed`, or cancelled as inactive, so the Login button returns to red when login is still needed.

Proof:
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py` passed.
- `python -m pytest tests\test_f061_run_legacy_first_checks_local.py -q` -> `44 passed`.
- `python -m pytest tests\test_f_legacy_webscrape_money_input.py tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_f_scanner_state.py tests\test_o_ui_operator_view.py -q` -> `155 passed`.
- Pytest printed the existing Windows temp `pytest-current` cleanup PermissionError after tests completed; tests themselves passed.

Verification status:
- Code fix applied.
- Isolated verification passed.
- Live loop verification confirmed for request consumption, visible normal F061 child startup, 60 second login hold, still-required parking, and return to normal pending-row scanning.
- Live authentication success remains unproven because the browser was not logged in during this proof window.

Live proof trigger:
- Operator presses Login in the Price List Queue UI while the active run has `login_backtrack_pending` rows.

Live proof artifacts:
- `out/systems/F/price_list_manager/live/f061_login_mode.requested`
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
- `out/systems/F/price_list_manager/live/f061_child_status.txt`
- `out/systems/F/price_list_manager/live/f061_child_stdout.log`
- `out/systems/F/price_list_manager/live/f061_child_stderr.log`
- `out/systems/F/live/feeder_legacy_sheet_health.csv`
- `out/systems/F/inbox/supplier_price_list_active_run.csv`

Live success condition:
- `live_cycle_events.csv` shows `login_mode_child_started` from FPM130 and `login_mode_hold_started` from F061.
- F061 child status/logs show the normal F061 subprocess running visible, not a separate Chrome maintenance window.
- After operator login, `f061_login_mode.requested` reaches `status=authenticated_backlog_remaining` or `status=drained`.
- `supplier_price_list_active_run.csv` login-backtrack count decreases, or the request remains `still_required` without completing login rows as false failures.

If the condition fails:
- Do not open a separate standalone Chrome login window.
- Keep the request on the normal F061 path.
- Inspect the newest F061 child stderr/stdout and `f061_login_mode_runtime` health row.
- If login still shows as required, leave rows parked and retry through the UI Login button/normal child boundary.

Current live owner note:
- Checked UTC: 2026-05-09T12:06:15Z.
- Old FPM owner was reloaded at a natural child boundary; no duplicate owner was left running.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` showed FPM owner `pid=32712`, state `running`, supplier `stax`, pending rows `22720`, notes `f061_child_started`.
- `out/systems/F/price_list_manager/live/f061_child_status.txt` showed child `pid=30816`, `browser_mode=minimized`, `browser_visibility=hidden`, started `2026-05-09T12:05:57Z`.
- `out/systems/F/price_list_manager/live/f061_login_mode.requested` showed `status=still_required`.
- `out/systems/F/inbox/supplier_price_list_active_run.csv` showed total `22720`, normal pending `22718`, login rows `2`.
- `out/locks/maintenance.requested` was cleared after reload.

Live proof result:
- `live_cycle_events.csv` contains `login_mode_child_started` at `2026-05-09T11:51:59Z`.
- `live_cycle_events.csv` contains `login_mode_hold_started` at `2026-05-09T11:52:02Z`.
- `live_cycle_events.csv` contains `login_mode_still_required` after the 60 second hold.
- Webscrape stderr showed the new 60 second hold: `BBP manual login required; keeping the visible scanner browser open for up to 60 seconds.`
- Because login was not completed, F061 left login rows parked and returned the request to `still_required`.
- After `still_required`, FPM stopped Login Mode and resumed normal pending-row scanning with a minimized child.

Next implementation phase:
- Phase 4 - when the operator is ready, press Login again, log in within the 60 second visible F061 window, and confirm `authenticated_backlog_remaining` or `drained`.

## Login Mode Phase 4 - No Automatic Visible Popups
Recorded UTC: 2026-05-09T12:30:00Z

Scope:
- Stop the old auth-attention path from repeatedly opening visible Chrome when BBP login is still required.
- Keep logged-out rows parked under the UI Login count until the operator presses Login.
- Keep all login recovery on the normal F061 child path.
- Do not change Google Sheets.

Changed files:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_fpm130_live_cycle.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- this coding plan

Implemented:
- FPM130 now defaults `FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION` to off.
- Outside active Login Mode, auth-required child logs no longer call the Windows show-window helper.
- Outside active Login Mode, scanner chunks with browser-block/login-required rows write `f061_auth_attention=deferred_login_mode` and leave the next child minimized.
- `still_required` login requests now explicitly clear stale login-mode env and return the next child to minimized/hidden mode.
- Active UI Login Mode remains the normal way to show the script-owned F061 browser.

Proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py -q` -> `29 passed`.
- Pytest printed the existing Windows temp `pytest-current` cleanup PermissionError after tests completed; tests themselves passed.

Verification status:
- Code fix applied.
- Isolated verification passed.
- Live loop verification confirmed for safe FPM reload and normal hidden/minimized children after a `still_required` Login Mode request.
- Live loop verification for the new `deferred_login_mode` event is parked pending the next browser-blocked chunk after the reload.

Live evidence:
- Old FPM owner `pid=32712` reached `drain_exit` at `2026-05-09T12:32:30Z` and stopped.
- New FPM owner `pid=24604` started at `2026-05-09T12:33:14Z` with the same command: `--chunk-rows 5 --sleep-seconds 10 --apply-next --auto-approve-next`.
- Post-reload F061 child starts were all minimized: `2026-05-09T12:33:15Z`, `2026-05-09T12:34:03Z`, `2026-05-09T12:34:50Z`, and `2026-05-09T12:35:40Z`.
- `out/systems/F/price_list_manager/live/f061_child_status.txt` showed `browser_mode=minimized|browser_visibility=hidden` for child `pid=29552`.
- Stax active rows continued moving: total `22629` at the latest check, with `4` rows parked under login backlog.

Live proof target:
- Trigger: the next post-reload F061 summary with `scanner_speed_browser_blocked_rows > 0`.
- Artifact to inspect: `out/systems/F/price_list_manager/live/live_cycle_events.csv`.
- Success condition: the matching post-reload `f061_auth_attention` event has `status=deferred_login_mode` and notes include `login_mode_button_required;next_child_browser_mode=minimized`.
- If it fails: do not open a separate Chrome window; inspect FPM130 auth-attention handling and keep normal child mode hidden until the UI Login button is pressed.

If the condition fails:
- Do not open a separate standalone Chrome login window.
- Do not force the launcher visible.
- Inspect `live_cycle_events.csv`, `f061_child_status.txt`, `f061_child_stdout.log`, and `f061_child_stderr.log`.

## Login Mode Phase 5 - Operator Hold Extension
Recorded UTC: 2026-05-09T12:45:00Z

Scope:
- Login Mode was entering the normal visible F061 child, but the 60 second hold was too short for real operator login.
- Keep the same normal script-owned F061 path.
- Do not open a separate Chrome window.

Changed files:
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_o_ui_operator_view.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- this coding plan

Implemented:
- UI Login Mode default hold changed from 60 seconds to 900 seconds.
- FPM130 fallback default hold changed from 60 seconds to 900 seconds.

Proof target:
- `python -m py_compile scripts\flows\O\O400_operator_ui.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py`
- `python -m pytest tests\test_o_ui_operator_view.py tests\test_fpm130_live_cycle.py -q`
- Re-request Login Mode after the current 60 second attempt finalizes, and confirm the next `login_mode_child_started` / `login_mode_hold_started` notes show `hold_seconds=900`.

Current live status:
- Current active Login Mode request began at `2026-05-09T12:39:55Z` with `hold_seconds=60`.
- It reached `status=holding` and child `pid=26860` started as `browser_mode=visible`.
- Stderr confirmed: `BBP manual login required; keeping the visible scanner browser open for up to 60 seconds.`
- The next live request must use `hold_seconds=900`.

## Login Mode Phase 6 - BBP Window Visibility Recovery
Recorded UTC: 2026-05-09T13:20:00Z

Scope:
- Fix Login Mode opening a Chrome window that immediately disappeared.
- Keep login recovery on the normal FPM130 -> F061 scanner-owned path.
- Do not use `FPM160_f061_visible_login_maintenance.py open`.
- Do not open a separate no-plugin Chrome window.

Root cause:
- The correct BBP/plugin Chrome profile was being launched, but Windows marked all automation Chrome top-level windows hidden.
- FPM130 marked the child as `visible` before Chrome existed, so later `BBP manual login required` evidence did not re-run the show routine.
- The show routine used `MainWindowHandle`, but hidden Chromium windows had real top-level handles while `MainWindowHandle` was unusable.
- Visible Login Mode could also attach to stale hidden specialist Chrome processes from previous failed attempts.

Changed files:
- `scripts/flows/F/_scanner_state.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_fpm130_live_cycle.py`
- this coding plan

Implemented:
- Added `BBP manual login required` / `manual login required` to the auth-required detector.
- When Login Mode is visible and auth evidence repeats while state is already `visible`, FPM130 now re-runs the show routine.
- The show routine now enumerates all matching Chrome top-level windows and restores them, instead of relying on `MainWindowHandle`.
- Visible Login Mode starts the F061 child with Windows `SHOWNORMAL`.
- Visible Login Mode force-cleans only specialist automation Chrome before launch, so it does not attach to stale hidden BBP windows. Normal non-login startup still preserves specialist Chrome.
- The date/support Chrome remains hidden in Login Mode; only `Chrome_UC136v2` / `BBPProfile1` is surfaced.

Proof:
- `python -m py_compile scripts\flows\F\_scanner_state.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py`
- `python -m py_compile scripts\flows\F\F061_run_legacy_first_checks_local.py`
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py -q` -> `81 passed`.
- Pytest printed the existing Windows temp `pytest-current` cleanup PermissionError after tests completed; tests themselves passed.

Live proof:
- Restarted FPM130 owner under the normal live command.
- Current owner: `pid=20092`, started `2026-05-09T13:16:46Z`.
- Current F061 child: `pid=26052`, `browser_mode=visible`, `browser_visibility=visible`.
- `live_cycle_events.csv` contains `login_mode_child_started` at `2026-05-09T13:16:45Z` and `login_mode_hold_started` at `2026-05-09T13:16:48Z`.
- Windows handle proof found visible BBP/plugin windows for `BBPProfile1/Chrome_UC136v2`, process `pid=16912`.
- Windows handle proof showed the no-plugin/support `Chrome_91_F061` windows remained hidden.

Verification status:
- Code fix applied.
- Isolated verification passed.
- Live window visibility confirmed.
- Login completion/backlog drain is not yet proven because the operator still needs to complete BBP/Amazon login in the visible scanner-owned Chrome window.

Next live verifier:
- Trigger: operator completes login in the visible BBP/plugin window during the current 900 second hold.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_login_mode.requested` and `out/systems/F/price_list_manager/live/live_cycle_events.csv`.
- Success condition: request moves to `authenticated_backlog_remaining` or `drained`, and FPM130 processes login backlog rows before returning to normal pending rows.
- If it fails: inspect `f061_child_stderr.log` for the exact auth evidence; do not use a separate Chrome window.

## Login Mode Phase 7 - Restore Legacy Scanner Chrome Profile
Recorded UTC: 2026-05-09T13:31:00Z

Scope:
- Operator reported the visible Login Mode Chrome was not the Chrome profile used by the scanner over the last few weeks.
- Stop flashing visible windows first.
- Restore the normal F061 scanner profile to the legacy scanner profile.

Root cause:
- Earlier Phase 2/6 work forced the scanner onto `Chrome_UC136v2` / `BBPProfile1` because that profile had the BuyBotPro extension manifest.
- The legacy scanner code path in `firstCheck.py` and `Webscrape.py` used `C:\Users\Luke\AppData\Local\Chrome_UC136` / `BBPProfile`.
- The visible-window filter also matched `Chrome_UC136v2` accidentally because `Chrome_UC136` is a substring of `Chrome_UC136v2`.

Changed files:
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_fpm130_live_cycle.py`
- this coding plan

Implemented:
- F061 default BBP browser profile restored to `C:\Users\Luke\AppData\Local\Chrome_UC136` / `BBPProfile`.
- `F061_REQUIRE_BBP_EXTENSION` now defaults off so the old working profile is not blocked only because it lacks the explicit BuyBotPro extension manifest.
- Login Mode show filter now targets exact `Chrome_UC136` and exact `--profile-directory=BBPProfile`, so it cannot surface `Chrome_UC136v2` / `BBPProfile1` by substring match.
- Current active Login Mode request was canceled to stop the flashing.

Proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\F061_run_legacy_first_checks_local.py`
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py -q` -> `82 passed`.
- Pytest printed the existing Windows temp `pytest-current` cleanup PermissionError after tests completed; tests themselves passed.

Live status:
- FPM130 restarted hidden after the fix.
- Current owner: `pid=19852`.
- Current F061 child: `pid=2184`.
- `f061_child_status.txt` shows `browser_mode=minimized|browser_visibility=hidden`.
- Window handle proof after the flash-stop showed scanner Chrome windows hidden.

Next live verifier:
- Trigger: the operator presses Login again from the UI.
- Artifact to inspect: visible Chrome command line/window handle.
- Success condition: visible Login Mode surfaces `Chrome_UC136` with `--profile-directory=BBPProfile`, not `Chrome_UC136v2` or `BBPProfile1`.
- If it fails: do not use a separate Chrome window; tighten the FPM130 Login Mode show filter and inspect the actual visible process command line.

## Login Mode Phase 8 - Return To Normal Scanner Path Only
Recorded UTC: 2026-05-09T14:06:00Z

Scope:
- Stop profile guessing and experimental visible-browser overrides.
- Login Mode must run the normal F061 scanner path, with only:
  - login backlog row selection
  - longer hold time for operator login
  - one initial show attempt, not repeated focus flashing

Implemented:
- Current Login Mode request reason set to `run_normal_scanner_path_long_wait_only`.
- Current child launched through normal `F061_run_legacy_first_checks_local.py`.
- Current Chrome command line confirmed normal scanner profile: `C:\Users\Luke\AppData\Local\Chrome_UC136` with `--profile-directory=BBPProfile`.
- Added `f061_login_mode_window_shown.marker` guard so repeated login-required log evidence does not keep forcing Chrome to the front.

Proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py`
- `python -m pytest tests\test_fpm130_live_cycle.py -q` -> `36 passed`.

Live status:
- Current FPM owner: `pid=29072`.
- Current F061 child: `pid=29784`.
- `f061_child_status.txt` shows `browser_mode=visible|browser_visibility=visible`.
- Current request has `hold_seconds=900`.

Next verifier:
- Trigger: operator completes login in the normal scanner Chrome window.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_login_mode.requested`.
- Success condition: request moves to `authenticated_backlog_remaining` or `drained`.
- If it fails: do not switch Chrome profiles again; inspect only the normal scanner logs and row selection.

## Login Mode Phase 9 - Recovery Plan After Dead Scan
Recorded UTC: 2026-05-09T15:25:00Z

Current evidence:
- Project root confirmed: `C:\Users\Luke\Desktop\SellerOne 2.0`.
- Latest live status is stale: `out/systems/F/price_list_manager/live/live_cycle_status.csv` shows `observed_utc=2026-05-09T14:08:17Z`.
- No current `FPM130_run_live_cycle.py` owner process was found.
- No current `F061_run_legacy_first_checks_local.py` child process was found.
- No current scanner Chrome process was found.
- `f061_login_mode.requested` still exists with `status=requested`, `hold_seconds=900`, and reason `run_normal_scanner_path_visible_parent`.
- Several zero-byte `f061_login_mode.requested.tmp.*` files remain from interrupted login attempts.
- Direct F061 login proof also produced hidden Chrome windows, so the issue is not solved by bypassing FPM.

Recovery objective:
- Get the Stax price-list scan running again first.
- Then rebuild Login Mode so it uses the exact same F061 scanner launch path as the regular scanner.
- Login Mode may only change:
  - row selection: login-backlog rows first
  - hold time: 900 seconds
  - visibility request: visible for the normal F061 browser
- Login Mode must not change:
  - Chrome executable
  - Chrome user-data-dir/profile
  - Webscrape/firstCheck profile logic
  - ownership model
  - Google Sheets

Phase 9A - Stabilise And Restart Normal Scanning
Allowed files:
- Runtime artifacts under `out/systems/F/price_list_manager/live/`
- Existing FPM/F061 scripts only if a startup blocker is found

Steps:
1. Stop any leftover FPM, F061, and specialist scanner Chrome processes if present.
2. Archive stale `live_cycle.lock` and `f061_child_status.txt` if their PIDs are not alive.
3. Set `f061_login_mode.requested` to inactive before restart, not `requested`.
4. Remove only stale zero-byte `f061_login_mode.requested.tmp.*` files after confirming no owner process is alive.
5. Start FPM130 with the normal live command and no Login Mode:
   - `python -u scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py --chunk-rows 5 --sleep-seconds 10 --apply-next --auto-approve-next`
6. Verify normal ownership:
   - `live_cycle.lock` has a live PID
   - `f061_child_status.txt` updates after restart
   - `live_cycle_status.csv` has `observed_utc` after the restart time
   - there is exactly one FPM owner and no duplicate F061 child

Success condition:
- Normal FPM owner is running and writing fresh heartbeat/status artifacts.
- Scanner resumes Stax work in minimized/hidden mode.
- No Login Mode or visible-browser behavior is active.

If it fails:
- Do not open a separate Chrome window.
- Inspect `fpm130_login_restart_stderr.log`, `f061_child_stderr.log`, stale lock content, and process ownership.

Phase 9B - Rebuild Login Mode Around The Normal Scanner Path
Allowed files:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `tests/test_fpm130_live_cycle.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
- this coding plan

Design rules:
- Add a single source of truth for the F061 child command/env used by both normal scan and Login Mode.
- Login Mode must call that same child launcher, not a separate maintenance helper and not direct manual Chrome.
- Remove or quarantine profile-forcing changes from Login Mode. The Chrome profile must come from the normal F061 code path.
- Remove repeated external window-show loops. They caused flashing and false visible states.
- In F061, visible Login Mode must mean the BBP browser is launched visibly from the start:
  - no `--start-minimized`
  - no `--window-position=-32000,-32000`
  - use a normal on-screen position/size at initial Chrome option level
  - keep the date/support browser hidden only if it is separate from the BBP browser
- FPM must record `visible_requested`, but must not claim `visible_confirmed` unless a top-level window handle for the normal scanner BBP Chrome is actually visible.

Proof:
1. Unit/isolated tests:
   - `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\F061_run_legacy_first_checks_local.py`
   - `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py -q`
2. Direct F061 Login Mode proof:
   - run one direct F061 login-mode child only after all old owners are stopped
   - success requires Windows handle proof that the normal scanner Chrome is visible
   - do not accept `browser_mode=visible` text alone as proof
3. FPM-owned proof:
   - create a Login Mode request from the UI path/request file
   - run FPM130 via `--run-once` first if possible
   - then restart normal FPM ownership only after proof
   - success requires the visible window command line to match the normal scanner command line and the request to move to `holding`

Live completion condition:
- FPM is running normally after the proof.
- Login Mode opens the same normal scanner browser that regular F061 uses.
- Operator can complete BBP/Amazon login in that window.
- `f061_login_mode.requested` moves to `authenticated_backlog_remaining` or `drained`.
- Backlog rows are processed before normal pending rows resume.

Phase 9C - UI And Operator Proof
Steps:
1. Confirm the UI Login button writes one active request with `hold_seconds=900`.
2. Confirm the UI count reflects login-backlog rows and does not require a separate Chrome helper.
3. Confirm that pressing Login while an owner is active waits for the next normal F061 child rather than killing/replacing the process mid-chunk.
4. Confirm failure states are visible:
   - `request_waiting`
 - `visible_failed`
 - `still_required`
 - `authenticated_backlog_remaining`
 - `drained`

## Login Mode Phase 9 Live Execution
Recorded UTC: 2026-05-09T15:57:06Z

Scope:
- Restore the dead Stax scan.
- Start Login Mode through the normal FPM130 -> F061 scanner path.
- Keep the visible browser as the normal scraper Chrome profile, not a separate maintenance Chrome.

Changed files:
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f_legacy_webscrape_money_input.py`
- `tests/test_fpm130_live_cycle.py`
- this coding plan

Implemented:
- Normal Stax scanning was restarted first with Login Mode inactive.
- F061 visible mode now launches the BBP browser on screen and brings the page target forward through Chrome DevTools.
- Webscrape now treats missing BBP iframe/container during visible Login Mode as login evidence and holds the same scanner browser for `hold_seconds=900` instead of returning immediately.
- Webscrape no longer refreshes the page every minute during the operator hold; it keeps the same browser surfaced and only does the final recheck refresh when the hold expires.
- FPM130 now targets the normal F061 default BBP profile when surfacing Login Mode Chrome: `C:\Users\Luke\AppData\Local\Chrome_UC136` / `BBPProfile`.
- FPM130 now uses the Chrome remote debugging port to surface the same scanner Chrome window when Windows has not assigned a normal top-level handle yet.
- FPM130 no longer marks the login window as shown two seconds after launch before Chrome is ready.

Proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\F061_run_legacy_first_checks_local.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f_legacy_webscrape_money_input.py tests\test_f061_run_legacy_first_checks_local.py -q` -> `102 passed`.
- Pytest printed the existing Windows temp `pytest-current` cleanup PermissionError after tests completed; tests themselves passed.

Live evidence from failed Login Mode attempt:
- Superseded at `2026-05-09T16:11:21Z` by Phase 9D reset below.
- The previous attempt did reach the normal scanner path, but it did not give the operator a stable login option.
- The operator saw repeated flashing, so the live Login Mode attempt was stopped.
- Root issue for tomorrow: treating `BBP iframe missing` on an Amazon product page as a Login Mode hold condition was too broad. It surfaced/held before a real Amazon or BBP login option was detected.

Verification status:
- Code fix applied.
- Isolated verification passed.
- Live Login Mode completion/backlog drain is not yet proven.
- Normal scanner ownership was restored in Phase 9D below.

Current operator step:
- None. Login Mode is canceled until the foolproof 2026-05-10 execution plan is applied.

Next verifier:
- Trigger: 2026-05-10 operator Login Mode execution after Phase 9D detector guard is implemented.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_login_mode.requested`, `out/systems/F/price_list_manager/live/live_cycle_events.csv`, and `out/systems/F/price_list_manager/live/f061_child_status.txt`.
- Success condition: a real login option is detected first, then the same normal F061 scanner child/browser is made visible once and held without flashing.
- If it fails: do not open a separate Chrome window; fix the earliest detector/surfacing branch that contradicted the F061 login rule.

Next action after this plan:
- Continue with Phase 9D on 2026-05-10.

## Login Mode Phase 9D - Reset To Normal Mode And Tomorrow Plan
Recorded UTC: 2026-05-09T16:11:21Z

Current reset:
- Login Mode request file: `out/systems/F/price_list_manager/live/f061_login_mode.requested`.
- Login Mode status was set to `canceled` because `paused` is not an inactive status in FPM130.
- Stale `live_cycle.lock`, stale `f061_child_status.txt`, and stale `f061_login_mode_window_shown.marker` from the flashing attempt were removed before restart.
- Normal FPM130 was restarted hidden/minimized with the regular command: `python -u scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py --chunk-rows 5 --sleep-seconds 10 --apply-next --auto-approve-next`.

Reset proof:
- FPM owner after reset: `pid=27272`, `start=2026-05-09T16:10:03Z`, latest observed heartbeat `2026-05-09T16:10:54Z`.
- Normal F061 child after reset: `pid=30624`, `browser_mode=minimized`, `browser_visibility=hidden`, started `2026-05-09T16:10:03Z`.
- Browser visibility state: `state=hidden`, `browser_state=HIDDEN`, `auth_state=LOGGED_IN`, `reason=child_started_minimized`.
- Live status row after reset: `state=running`, `active_supplier_id=stax`, `last_action=resume_f061_active_run`, `last_action_status=scanner_running`, `pending_rows=22597`.
- Login Mode request after reset: `status=canceled`, `reason=reset_normal_mode_until_2026_05_10_login_plan`.

Tomorrow execution trigger:
- Date: 2026-05-10.
- Preferred operator window: 09:15 Europe/London, or the first time the operator is ready to watch Login Mode.
- Durable due check: `project_control/DUE_CHECK_REGISTER.csv` row `F_STAX_LOGIN_MODE_20260510_EXECUTE`.

Tomorrow implementation plan:
1. Start from normal hidden FPM only. Confirm there is exactly one FPM owner and one normal F061 child before any Login Mode work.
2. Keep `FPM160_f061_visible_login_maintenance.py open` out of the path. It is not an acceptable BBP login solution for this task.
3. Change Login Mode so it does not make Chrome visible just because the BBP iframe is missing.
4. Park rows as login-backtrack pending when BBP evidence is missing, but keep the browser hidden and return to normal scanning until a real login option is detected.
5. Treat these as real login-option evidence:
   - Amazon URL contains `/ap/signin`.
   - Amazon login fields/buttons are visible, such as email, password, continue, or sign-in submit.
   - BBP login fields/buttons are visible, such as login email, login password, or login button.
   - Amazon security challenge, OTP, approval, CAPTCHA, or explicit sign-in-required page is visible.
6. When real login-option evidence is detected, set the request/status to `login_option_detected`.
7. Surface the same normal F061 scanner-owned Chrome once, using the same normal profile path. Do not start a separate Chrome and do not force a different profile.
8. Hold that same browser for 900 seconds for operator login. Do not run repeated foreground loops that cause flashing.
9. After the hold, refresh/recheck once. If login is active, process the login-backtrack backlog first, backdate/merge recovered evidence into the original rows, then resume the normal list.
10. If the real login option is not detected, the correct behavior is hidden normal scanning plus parked rows, not visible flashing.

Proof gates for tomorrow:
- Run focused tests for F061, Webscrape, and FPM130.
- Run isolated direct proof only when no FPM/F061 owner is already active.
- Run the live proof through FPM130 request consumption, not a manual Chrome helper.
- Success requires `login_option_detected` before visibility and a same-profile normal F061 browser command line.
- Failure action: cancel Login Mode, restore normal hidden FPM, and fix the detector branch before trying again.

## Deferred Idea - Assisted Amazon Login Prefill
Recorded UTC: 2026-05-09T12:10:00Z

Add this only after Phase 4 proves the current Login Mode works end to end.

Idea:
- In Login Mode, the normal script-owned F061 browser can prefill the Amazon email/password fields, submit the first login step, then stop and wait for the operator to enter the verification code or approve the sign-in challenge.
- This should reduce the manual work to the code/challenge step only.

Hard rules:
- Do not implement until the current Login Mode is live-proven.
- Do not open a separate Chrome window.
- Do not store Amazon credentials in repo files, plan files, CSV outputs, logs, or screenshots.
- Credentials must come only from a local secret store or ignored local secret file with an explicit setup step.
- Never log the email/password values.
- Never attempt to bypass 2FA, OTP, CAPTCHA, app approval, or Amazon security checks.
- The browser must pause visibly for the operator at the code/challenge step.

Design notes for later:
- Add a UI toggle such as `Assist Login` separate from the current `Login` button.
- Add a preflight check that credentials are configured locally before enabling the toggle.
- Add event rows such as `login_mode_prefill_started`, `login_mode_waiting_for_code`, and `login_mode_prefill_blocked`.
- Add health row `f061_login_prefill_secret_state`.
- If prefill fails or Amazon shows a different security screen, fall back to the current manual Login Mode and keep rows parked.

## Login Mode Phase 9E - Same-Path Browser Correction
Recorded UTC: 2026-05-11T10:58:00Z

User report:
- The Login Mode feature still does not work live.
- It runs, but it opens or surfaces the wrong browser/profile path, flashes windows, and does not use the same logged-in scanner browser as the normal run.
- Required correction: Login Mode must run exactly like the normal F061 scanner except for:
  - selecting login-backtrack rows first
  - holding longer when a real login option is detected
  - surfacing the already-created normal F061 BBP browser only after real login evidence

Root-cause target:
- FPM130 currently changes the child to visible immediately when `f061_login_mode.requested` is active.
- FPM130 also has external window-surfacing loops that can show the wrong Chrome/profile or create flashing.
- F061 has a visible-login cleanup branch that can kill specialist Chrome before start when Login Mode is visible.
- Webscrape currently treats missing BBP iframe/container as a visible-login hold condition, which is too broad and can surface before a real login page exists.

Allowed files:
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `tests/test_fpm130_live_cycle.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f_legacy_webscrape_money_input.py`
- this coding plan

Implementation rule:
- FPM130 must keep Login Mode on the normal child launch path and must not force visible startup.
- F061/Webscrape must own the already-created BBP driver and surface only that driver after real Amazon/BBP login-option evidence.
- No `FPM160_f061_visible_login_maintenance.py open`.
- No separate Chrome launch.
- No profile override away from the normal F061 profile.
- No repeated external show loops for Login Mode.

Proof plan:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py`
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py tests\test_f_legacy_webscrape_money_input.py -q`
- Runtime proof remains pending until the next normal FPM/F061 boundary with an operator Login Mode request.

Implementation completed UTC: 2026-05-11T11:14:36Z

Changed:
- FPM130 no longer forces `F061_BACKGROUND_BROWSER_MODE=visible` for an active Login Mode request.
- FPM130 keeps the child on `F061_BACKGROUND_BROWSER_MODE=minimized`, `F061_SHOW_WINDOWS=0`, and `FPM_LIVE_HIDE_SCRAPER_WINDOWS=1` while still passing `F061_LOGIN_MODE=1`, request path, and hold seconds.
- FPM130 records login-mode auth visibility as scanner-owned evidence and does not call its external Chrome show helper for Login Mode.
- F061 no longer force-cleans specialist Chrome just because Login Mode is visible. Cleanup now requires explicit recovery env `F061_FORCE_CLEAN_SPECIALIST_CHROME_FOR_LOGIN=1`.
- Webscrape now treats missing BBP iframe/container as parked evidence unless a real login option is detected.
- Webscrape real login-option evidence includes Amazon `/ap/signin`, MFA/CVF/OTP/CAPTCHA/sign-in controls, or BBP login email/password/button controls.
- When real login-option evidence is present, Webscrape surfaces the already-created scanner-owned BBP driver once and holds it for operator login.

Isolated proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f061_run_legacy_first_checks_local.py tests\test_f_legacy_webscrape_money_input.py -q` -> `104 passed`.
- Pytest emitted the known Windows temp `pytest-current` cleanup PermissionError after tests completed; the test result itself passed.

Runtime state at proof time:
- FPM owner is running: `live_cycle.lock` pid `27972`, heartbeat `2026-05-11T11:13:19Z`.
- Current F061 child is normal hidden mode: pid `25076`, supplier `stax`, `browser_mode=minimized`, `browser_visibility=hidden`.
- Login Mode request file is inactive/canceled, so no live login proof was attempted in this patch.

Runtime proof still required:
- Trigger: operator presses Login in the Price List Queue UI while the normal FPM owner is active and login-backtrack rows exist.
- Success condition: F061 selects login-backtrack rows first, stays hidden until real login-option evidence, then surfaces the same `Chrome_UC136` / `BBPProfile` scanner-owned browser once without flashing.
- If condition fails: cancel Login Mode, keep FPM normal hidden, inspect newest `f061_child_stderr.log`, `f061_child_status.txt`, and `live_cycle_events.csv`, and fix the detector branch before retrying.

Runtime owner reload proof:
- F-only drain request written at `2026-05-11T11:18:13Z` with `action=reload` and `exit_after_drain=1`.
- Old FPM owner pid `27972` exited at boundary; `live_cycle.lock` released and temporary reload request cleared.
- Normal launcher restarted FPM with the patched code loaded: owner pid `4424`, start `2026-05-11T11:18:57Z`.
- Current child is normal scanner path: pid `26472`, supplier `stax`, `browser_mode=minimized`, `browser_visibility=hidden`, started `2026-05-11T11:18:57Z`.
- Login Mode request remains inactive/canceled, so live operator login proof is still pending.

## Login Mode Phase 9F - Hider Conflict Correction
Recorded UTC: 2026-05-11T12:19:00Z

Live evidence from operator click:
- Operator Login request recorded at `2026-05-11T11:44:51Z`.
- Login Mode child started at `2026-05-11T11:45:31Z` on the corrected same-path child setup: `browser_mode=normal_minimized_until_login_option`.
- First patched attempt selected 5 login-backtrack rows and kept the child hidden, but status ended as `still_required`.
- Root cause found: missing BBP iframe in explicit Login Mode is login-required evidence even when no literal login form selector is visible.
- Second attempt after Webscrape detector patch reached `F061_LOGIN_OPTION_DETECTED login_mode_missing_bbp_iframe`, but the browser remained hidden because a stale `f_hide_scraper_windows.ps1` helper was still running.

Changed:
- Webscrape now surfaces the already-created scanner-owned browser when `F061_LOGIN_MODE=1` and missing BBP iframe/container is detected.
- FPM now treats a Login Mode blocked chunk as `deferred_login_mode` so it does not convert the failure into a separate normal visible-child path.
- FPM Login Mode child env now uses `FPM_LIVE_HIDE_SCRAPER_WINDOWS=0` with `F061_BACKGROUND_BROWSER_MODE=minimized`, so the child starts same-path/minimized but no hider fights Webscrape later.
- FPM only calls the external show helper at child start when `F061_BACKGROUND_BROWSER_MODE=visible`; Login Mode minimized start stops the hider but does not show immediately.

Isolated proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f_legacy_webscrape_money_input.py -q` -> `58 passed`.
- Pytest again emitted the known Windows temp `pytest-current` cleanup PermissionError after tests completed; the tests themselves passed.

Runtime state:
- Current Login Mode child pid `25768` is still holding with request status `holding`.
- Existing correct scanner-owned browser is pid `28168`: `C:\Chrome_UC136\bin\chrome.exe`, `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136`, `--profile-directory=BBPProfile`.
- Stale hider was stopped manually and the existing scanner-owned browser was surfaced by DevTools; call returned `True`.
- Authentication is not yet proven. No `BBP iframe/container became available` or authenticated request status has been observed yet.

Next proof gate:
- User must complete login in the visible `Chrome_UC136` / `BBPProfile` browser only.
- Then inspect `out/systems/F/price_list_manager/live/f061_login_mode.requested`, `out/systems/F/price_list_manager/live/f061_child_stderr.log`, and `out/systems/F/price_list_manager/live/live_cycle_events.csv`.
- Success condition: request status becomes `authenticated`, `authenticated_backlog_remaining`, `completed`, or `consumed`, or stderr logs `BBP iframe/container became available`.
- If the browser is not visible to the user, cancel the current hidden Login Mode attempt, reload FPM after the child is terminal, and retry with Phase 9F loaded.

## Login Mode Phase 9G - Windows Surface and Trigger Correction
Recorded UTC: 2026-05-11T12:34:00Z

Live evidence:
- Operator reported no Chrome browser was visible during Login Mode hold.
- Correct scanner-owned BBP Chrome was running, but started with `--start-minimized --window-position=-32000,-32000`.
- Manual WinAPI enumeration found the Amazon Chromium window for the scanner-owned `Chrome_UC136` / `BBPProfile` process and moved it on-screen.
- Restarted FPM through normal launcher after canceling the inaccessible hidden child so the Phase 9F code loaded.
- New owner pid `10732`; new F061 child pid `20776`; correct BBP Chrome root pid `5660`.
- New attempt reached `F061_LOGIN_OPTION_DETECTED login_mode_missing_bbp_iframe` and is holding for user login.

Additional root cause:
- FPM auth visibility did not treat `F061_LOGIN_OPTION_DETECTED`, `BBP/Amazon login option detected`, or `login_mode_missing_bbp_iframe` as login-required visibility evidence.
- Scanner DevTools surfacing alone can report success while Windows still keeps the Chromium HWND hidden/off-screen.

Changed:
- Webscrape now runs a Windows HWND show/move/focus step for the existing BBP profile Chrome after normal scanner-owned Login Mode surfacing.
- FPM show helper now restores and moves the existing BBP profile Chrome window instead of only calling ShowWindow.
- FPM Login Mode auth visibility now invokes the scanner-owned show helper once when login-required evidence is seen.
- Shared F scanner auth-state tokens now include the exact Login Mode evidence lines.

Isolated proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\_scanner_state.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f_legacy_webscrape_money_input.py tests\test_f_scanner_state.py -q` -> `61 passed`.
- Pytest emitted the known Windows temp `pytest-current` cleanup PermissionError after tests completed; the test run returned success.

Runtime proof status:
- Current live attempt is holding for user login on scanner-owned BBP Chrome pid `5660`.
- The current owner loaded Phase 9F but not the final Phase 9G shared-token change, so after this hold ends the FPM owner must be reloaded once more to load the token trigger correction.
- Authentication is not yet proven: no `BBP iframe/container became available` line has been observed yet.

Next proof gate:
- Success condition: user completes login in the currently surfaced `Chrome_UC136` / `BBPProfile` browser and stderr logs `BBP iframe/container became available` or request state becomes authenticated/completed/consumed.
- If this hold times out or the browser is still not visible, reload FPM after the child is terminal so Phase 9G is loaded, then retry Login Mode from the normal scanner path.

## Login Mode Phase 9G Live Retry - Visibility Confirmed
Recorded UTC: 2026-05-11T12:50:00Z

Evidence:
- Previous hold timed out at `2026-05-11 13:45:54` with `BBP iframe/container manual hold timed out; login is still required`.
- FPM was reloaded through the normal launcher so Phase 9G trigger handling loaded.
- Fresh owner pid `30192`, fresh child pid `30648`, correct scanner-owned BBP Chrome pid `15572`.
- New Login Mode hold started at `2026-05-11T12:47:50Z`.
- New login-required evidence appeared: `F061_LOGIN_OPTION_DETECTED login_mode_missing_bbp_iframe` and `BBP/Amazon login option detected`.
- Browser visibility is confirmed by `out/systems/F/price_list_manager/live/f061_child_status.txt`: `browser_visibility=visible`.
- Visibility state is confirmed by `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`: `state=visible|browser_state=VISIBLE|auth_state=LOGIN_REQUIRED|reason=auth_required_scanner_owned`.

Known follow-up:
- The currently running owner was started before the event-spam patch, so `live_cycle_events.csv` may repeat `auth_required_scanner_owned` every poll during this hold.
- The event-spam patch has isolated proof (`61 passed`) but will only load after the next FPM reload.

Next proof gate:
- Due time: `2026-05-11T13:03:18Z` / `2026-05-11 14:03:18 Europe/London`.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_child_stderr.log`.
- Success condition: log contains `BBP iframe/container became available` or request state becomes authenticated/completed/consumed.
- Failure action: if it times out again, classify Login Mode as visible-but-auth-unresolved, preserve the normal scanner path, and inspect the actual browser page state before changing scanner logic again.

## Login Mode Phase 9H - False Visible Status Root Cause
Recorded UTC: 2026-05-11T12:56:00Z

User evidence:
- Operator reported the browser was still not visible even though runtime artifacts said `browser_visibility=visible`.

Root cause:
- `f061_browser_visibility_state.txt` and `f061_child_status.txt` were treating a successful show attempt as proof.
- Actual Windows HWND inspection showed the Amazon Chromium windows were still hidden and off-screen at `-32000,-32000`.
- The earlier show logic moved IME helper windows, not the real hidden Chromium page windows.

Live recovery applied:
- Targeted scanner-owned Chrome pid `15572` only (`Chrome_UC136` / `BBPProfile`).
- Enumerated the titled Chromium HWNDs and forced visible window style, normal placement, restore/show commands, topmost/notopmost move, and foreground activation.
- Post-recovery HWND evidence showed the Amazon Chromium windows visible on screen at `-8,-8,1928,1040`.

Permanent code change:
- FPM show helper now targets titled Chrome/Amazon/Chromium windows and applies visible style plus `SetWindowPlacement`, not only `ShowWindowAsync`.
- Webscrape Login Mode surfacing now uses the same stronger HWND restore path.
- This makes the code fix the real hidden/off-screen window, not just write a visible status file.

Isolated proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\_scanner_state.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f_legacy_webscrape_money_input.py tests\test_f_scanner_state.py -q` -> `61 passed`.

Runtime proof status:
- Current child pid `30648` remains in manual hold and has not yet logged `BBP iframe/container became available`.
- Authentication is not yet proven.
- Current owner does not have the final Phase 9H code loaded; it was manually recovered live. The next Login Mode attempt after reload will test the permanent fix.

Next proof gate:
- Due time: current hold expiry from `2026-05-11 13:48:18 Europe/London` is `2026-05-11 14:03:18 Europe/London`.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_child_stderr.log`.
- Success condition: `BBP iframe/container became available` or request state authenticated/completed/consumed.
- If the user still cannot see the browser after the Phase 9H live recovery, stop treating artifacts as proof and inspect Windows session/desktop ownership before further scanner changes.

## Login Mode Phase 9I - Visible Launch Fix
Recorded UTC: 2026-05-11T13:04:00Z

User evidence:
- Operator still had nothing visible to log in to after HWND recovery attempts.
- Session check showed FPM, F061, Chrome, and Explorer were all in active console session `1`, so this was not a disconnected-session issue.

Root cause:
- Login Mode was still launching scanner-owned BBP Chrome with `--start-minimized --window-position=-32000,-32000`.
- This Chrome build/session did not reliably recover a user-visible window after that launch state, even when DevTools and WinAPI reported normal/visible state.

Changed:
- Active Login Mode now sets `F061_BACKGROUND_BROWSER_MODE=visible` and `F061_SHOW_WINDOWS=1` while keeping the same normal F061 child path and the same BBP profile (`Chrome_UC136` / `BBPProfile`).
- Normal non-login scanner runs remain minimized/hidden.
- Login Mode child-start event wording was updated from `normal_minimized_until_login_option` to `visible_from_start` for future owners.
- The stronger HWND restore code remains in FPM/Webscrape as a fallback, but the primary fix is to avoid creating the login browser off-screen in the first place.

Isolated proof:
- `python -m py_compile scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\_scanner_state.py` passed.
- `python -m pytest tests\test_fpm130_live_cycle.py tests\test_f_legacy_webscrape_money_input.py tests\test_f_scanner_state.py -q` -> `61 passed`.

Live proof:
- Old hidden child pid `30648` was terminated after reload request because the operator had no visible browser.
- FPM reloaded normally and restarted owner pid `9752`.
- New Login Mode child pid `12960` launched correct scanner-owned BBP Chrome pid `31620`.
- Chrome command line for pid `31620` uses `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136`, `--profile-directory=BBPProfile`, `--window-size=1400,900`, and `--window-position=80,80`.
- Chrome command line for pid `31620` does not include `--start-minimized` or `--window-position=-32000,-32000`.
- Child status shows `browser_mode=visible|browser_visibility=visible`.

Next proof gate:
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_child_stderr.log`.
- Success condition: user completes login in visible Chrome and log contains `BBP iframe/container became available`, or request state becomes authenticated/completed/consumed.
- If the browser is still not visible with pid `31620` launched at `80,80`, stop changing scanner code and inspect Windows desktop/window manager state with the operator physically present.

## Login Mode Phase 9J - Login Button Detector Proof
Recorded UTC: 2026-05-11T13:08:00Z

User request:
- Proceed until Login Mode can detect the login button/control.

Live evidence before patch:
- Attached to the current script-owned Chrome via DevTools port `64224` while F061 Login Mode was active.
- Current Amazon page had a visible `Hello, sign in Account & Lists` link with an `/ap/signin` URL.
- F061 did not count that as login evidence and instead logged only `login_mode_missing_bbp_iframe`.

Changed:
- Webscrape `_login_option_evidence` now treats Amazon `/ap/signin` and `openid.mode=checkid_setup` links as login evidence.
- Body-text fallback now also recognizes `hello, sign in` and `sign in account & lists`.
- Added focused unit proof for Amazon sign-in link detection.

Isolated proof:
- `python -m py_compile scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\_scanner_state.py` passed.
- `python -m pytest tests\test_f_legacy_webscrape_money_input.py tests\test_fpm130_live_cycle.py tests\test_f_scanner_state.py -q` -> `62 passed`.

Live proof:
- Reloaded FPM through the normal marker path to load the detector fix.
- Fresh FPM owner pid `31668`, fresh F061 child pid `30348`, scanner-owned BBP Chrome pid `6220`.
- Chrome pid `6220` uses `Chrome_UC136` / `BBPProfile` and visible launch flags (`--window-position=80,80`), with no `--start-minimized` and no `--window-position=-32000,-32000`.
- At `2026-05-11 14:07:15`, `out/systems/F/price_list_manager/live/f061_child_stderr.log` recorded: `F061_LOGIN_OPTION_DETECTED selector:a[href*='/ap/signin']`.

Status:
- Login button/control detection in Login Mode is proven.
- Authentication itself is not part of this proof and remains operator-dependent.

## Login Mode Phase 9K - Correct BBP Login Target And Visible Chrome
Recorded UTC: 2026-05-11T13:34:22Z

User correction:
- The Phase 9J Amazon `/ap/signin` detector was a false proof.
- The required Login control is inside the BuyBotPro extension panel where the dashboard Yes/No evidence appears, not the Amazon account header.

Root cause:
- The live scanner was using `C:\Users\Luke\AppData\Local\Chrome_UC136` / `BBPProfile`.
- That profile did not expose the BuyBotPro extension panel.
- The BuyBotPro extension manifest was present under `C:\Users\Luke\AppData\Local\Chrome_UC136v2\BBPProfile1`.
- Even with visible Chrome flags, the hidden FPM launcher could create the BBP Chrome window with a hidden/minimized Windows style.

Changed:
- F061 default BBP profile is now `Chrome_UC136v2` / `BBPProfile1`.
- Legacy `firstCheck.py` and standalone `Webscrape.py` BBP Chrome paths were aligned to the same profile.
- Webscrape login evidence no longer treats Amazon `/ap/signin`, Amazon MFA/CVF, or `Hello, sign in` body text as BBP login evidence.
- Scanner auth-state parsing no longer treats `login_mode_missing_bbp_iframe` or `BBP/Amazon login option detected` as a valid BBP login trigger.
- F061 Login Mode now forces the BBP Chrome process startup show state to normal when `F061_BACKGROUND_BROWSER_MODE=visible`.
- FPM/Webscrape HWND surfacing now uses `GetWindowLongPtr` / `SetWindowLongPtr`, sets `WS_VISIBLE`, and clears `WS_MINIMIZE`.

Isolated proof:
- `python -m py_compile scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\legacy_scanner_2_1\firstCheck.py scripts\flows\F\_scanner_state.py` passed.
- `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_f_legacy_webscrape_money_input.py tests\test_fpm130_live_cycle.py tests\test_f_scanner_state.py -q` -> `111 passed`.

Live proof:
- Old wrong-profile FPM/F061/Chrome tree was stopped.
- Fresh owner pid `31304`, child pid `18680`, and scanner-owned Chrome pid `24424` are running.
- Chrome pid `24424` command line uses `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136v2` and `--profile-directory=BBPProfile1`.
- DevTools shows the BuyBotPro extension service worker `chrome-extension://docdmgijbdlobilamkipaleciekbgbgl/...`.
- DevTools shows the BBP login iframe `https://me.buybotpro.com/Login?...`.
- `out/systems/F/price_list_manager/live/f061_child_stderr.log` records `F061_LOGIN_OPTION_DETECTED selector:#loginEmail,#loginPassword,#loginBtn` at `2026-05-11 14:31:34`.
- Current visible HWND proof after manual recovery: scanner Chromium hwnd `13765828` is visible at `-8,-8,1928,1040`.

Status:
- Correct BBP login-button detection is proven.
- Current login window is visible for operator login.
- Authentication/backlog merge is not yet proven and remains operator-dependent.
- The permanent HWND surfacing patch was applied after the current child started; it is isolated-tested but will load on the next FPM/F061 owner.

Next proof gate:
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_login_mode.requested` and `out/systems/F/price_list_manager/live/f061_child_stderr.log`.
- Success condition: after operator login, request status becomes `authenticated`, `authenticated_backlog_remaining`, `completed`, `consumed`, or `drained`, or stderr logs `BBP iframe/container became available` after login.
- Failure action: if this hold times out or the visible window disappears, reload FPM once to load Phase 9K surfacing code and retry through the same normal F061 Login Mode path. Do not use `FPM160_f061_visible_login_maintenance.py open`.

## Login Mode Phase 9L - Normal-Run Profile Comparison
Recorded UTC: 2026-05-11T13:56:30Z

User request:
- Switch off Login Mode and monitor a normal scanner run because the visible browser was steady but appeared to be the wrong Chrome/account.

Action taken:
- Cancelled `out/systems/F/price_list_manager/live/f061_login_mode.requested` at `2026-05-11T13:49:06Z`.
- Removed `out/systems/F/price_list_manager/live/f061_visible_login.requested`.
- Left the normal FPM owner running.

Normal-run evidence:
- Current FPM owner pid `31304`.
- Normal F061 child pid `29452` is running with `browser_mode=minimized` / `browser_visibility=hidden`.
- Current scanner Chrome pid `22380` is script-owned by child pid `29452`.
- Chrome pid `22380` launches `C:\Chrome_UC136\bin\chrome.exe` with `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136v2` and `--profile-directory=BBPProfile1`.
- `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt` reports `auth_state=LOGGED_IN`, but this is the v2 profile the operator says is not the correct visible account/browser.

Profile comparison:
- `C:\Users\Luke\AppData\Local\Chrome_UC136\BBPProfile`: exists, profile name `Luke`, no Google email found in Preferences, BBP extension folder not found.
- `C:\Users\Luke\AppData\Local\Chrome_UC136\Profile 2`: exists, profile name `Your Chromium`, Google email `laprice90@gmail.com`, BBP extension folder exists.
- `C:\Users\Luke\AppData\Local\Chrome_UC136v2\BBPProfile1`: exists, profile name `Person 1`, Google email `laprice90@gmail.com`, BBP extension folder exists.

Conclusion:
- Phase 9K correctly found the BBP login iframe/button, but it changed the normal scanner browser identity too.
- Do not retry Login Mode until the intended normal scanner profile is confirmed and the F061 defaults are corrected to match it.

Next proof gate:
- Artifact to inspect: live F061 process command line and `out/systems/F/price_list_manager/live/f061_child_stderr.log`.
- Success condition: after profile correction, normal hidden F061 and visible Login Mode both launch the same operator-approved Chrome profile, then Login Mode detects `#loginEmail,#loginPassword,#loginBtn`.
- Failure action: if the corrected profile still lacks the BBP panel, stop and inspect the chosen Chrome profile's extension/session state before changing scanner logic.

## Login Mode Phase 9M - Match Price List Manager Shortcut Profile
Recorded UTC: 2026-05-11T14:25:00Z

User evidence:
- `C:\Users\Luke\Desktop\Price List Manager.lnk` was the shortcut used for the old scanner.
- Shortcut target: `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1\run_firstCheck.bat`.
- Shortcut working directory: `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1`.
- The old `run_firstCheck.bat` runs `python firstCheck.py`.
- Old `firstCheck.py` launches BBP Chrome as `C:\Chrome_UC136\bin\chrome.exe` with `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136` and `--profile-directory=BBPProfile`.

Changed:
- F061 default BBP profile restored to `Chrome_UC136` / `BBPProfile`.
- FPM130 child environment defaults restored to `Chrome_UC136` / `BBPProfile`.
- Legacy scanner copy `firstCheck.py` and standalone `Webscrape.py` restored to `Chrome_UC136` / `BBPProfile`.
- Focused tests updated so the default profile expectation matches the shortcut.

Static proof:
- `python -m py_compile scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\legacy_scanner_2_1\firstCheck.py scripts\flows\F\_scanner_state.py` passed.
- `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_f_legacy_webscrape_money_input.py tests\test_fpm130_live_cycle.py tests\test_f_scanner_state.py -q` -> `111 passed`.

Live proof:
- Reloaded FPM through its drain boundary with `out\locks\maintenance.requested` `action=reload` / `exit_after_drain=1`.
- Fresh FPM owner pid `15952` started from `run_F_price_list_manager_cycle.bat`.
- Normal hidden scanner child pid `29108` launched scanner Chrome pid `25024`.
- Chrome pid `25024` used `C:\Chrome_UC136\bin\chrome.exe --user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136 --profile-directory=BBPProfile`.
- Retried Login Mode through normal FPM boundary.
- Visible Login Mode child pid `20948` launched Chrome pid `30316` with the same `Chrome_UC136` / `BBPProfile` profile and visible window flags.

Result:
- Matching the Price List Manager shortcut profile is proven.
- Login-button detection is not proven with this profile.
- DevTools target list for current Login Mode browser showed Amazon page/iframes only and no `chrome-extension://docdmgijbdlobilamkipaleciekbgbgl` service worker.
- Profile inspection showed `Chrome_UC136\BBPProfile` does not contain the BuyBotPro extension id `docdmgijbdlobilamkipaleciekbgbgl`.
- `Chrome_UC136\Profile 2` does contain the BuyBotPro extension id and is signed into `laprice90@gmail.com`.
- The retry request was cancelled at `2026-05-11T14:23:07Z`; FPM returned to normal hidden scanner mode with child pid `29720`.

Next proof gate:
- Trigger: operator decides whether the real working BBP scanner profile is `Chrome_UC136\Profile 2` despite the shortcut source code saying `BBPProfile`, or installs/enables BuyBotPro in `Chrome_UC136\BBPProfile`.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_child_stderr.log` after the next approved Login Mode retry.
- Success condition: visible Login Mode browser uses the operator-approved profile and logs `F061_LOGIN_OPTION_DETECTED selector:#loginEmail,#loginPassword,#loginBtn`.
- Failure action: if neither profile loads the BBP extension panel, pause Login Mode attempts and inspect Chrome extension installation state directly before changing scanner logic again.

## Login Mode Phase 9N - Old Scanner Baseline Comparison
Recorded UTC: 2026-05-11T14:48:00Z

User request:
- Stop looping on Login Mode attempts and go back to basics by comparing the old working shortcut scanner with the current F061/FPM path.

Old shortcut reference:
- Shortcut: `C:\Users\Luke\Desktop\Price List Manager.lnk`.
- Target batch: `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1\run_firstCheck.bat`.
- Old batch loops `python firstCheck.py` in `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1`.
- Old `firstCheck.py` waits 5 seconds, then starts one visible BBP driver and one visible date driver for the whole run.
- Old BBP launch: `C:\Chrome_UC136\bin\chrome.exe`, `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136`, `--profile-directory=BBPProfile`, `--log-level=3`.
- Old BBP driver window is explicitly placed on-screen at `0,0` with size `1280x720`.
- Old date driver uses `C:\Users\Luke\AppData\Local\Chrome_91` / `Profile 1` and is placed on-screen at `1280,0`.

Current F061/FPM differences found:
- FPM runs short child chunks, currently 5 rows per child, instead of one long-lived scanner run.
- Each F061 child starts and closes BBP/date browser drivers; the old shortcut keeps the drivers alive for the whole scanner run.
- Current normal mode adds hidden/minimized Chrome flags and off-screen window placement.
- Current Login Mode changes child environment flags and has extra request-file/state-machine logic before and after F061.
- Current embedded legacy `firstCheck.py` hides windows by default unless `F061_SHOW_WINDOWS=1`.
- Current F061 controller uses date profile `Chrome_91_F061` / `F061Profile`; the old shortcut uses `Chrome_91` / `Profile 1`.
- Current Webscrape has added Login Mode hold/detection logic and returns `BBP_LOGIN_REQUIRED` when BBP login remains unresolved.

Runtime evidence:
- Last confirmed successful BBP scrape remains `2026-05-09T10:06:37Z`.
- On `2026-05-11`, normal scanner chunks continue processing catalog/API rows, but browser scrape attempts have `scrape_success_rows=0`.
- Recent stderr shows the BBP iframe is sometimes found, but the BBP login form remains present after the automatic login attempt.
- Later attempts often fail earlier with `No BBP iframe` or `BBP_LOGIN_REQUIRED`.

Working theory:
- The scanner is not completely broken; the non-browser part is still running.
- The BBP scrape path is not currently proven healthy.
- The most important mismatch is no longer just the Chrome exe/profile string. It is the lifecycle: current FPM repeatedly creates short-lived browser sessions and wraps them with hidden/login-mode control, while the old shortcut used one visible long-lived browser session.

Next proof gate:
- Trigger: before changing code again, run a controlled no-Sheets diagnostic probe at an FPM maintenance boundary.
- Artifact to inspect: a probe log under `out/systems/F/diagnostics/` plus `out/systems/F/price_list_manager/live/f061_child_stderr.log`.
- Success condition: exact old-style driver launch opens the BBP panel/login fields in `Chrome_UC136` / `BBPProfile` without FPM hidden/login wrappers.
- Failure action: if the exact old-style probe also lacks BBP, stop changing F061 logic and repair the Chrome profile/extension state first. If the old-style probe works, change F061/FPM toward the old persistent visible-driver lifecycle for Login Mode proof.

## Login Mode Phase 9O - Normal-Mode 10-Row Practice Proof
Recorded UTC: 2026-05-11T15:31:00Z

User request:
- Pull 10 successful historical scrapes into a local practice list and get normal mode working fully before returning to Login Mode.

Practice inputs:
- Practice list: `out/systems/F/diagnostics/f061_success_scrape_practice_list_20260511T150019Z.csv`.
- Source evidence: `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`.
- Rows: 10 historical `scrape_success=True` ASINs from `2026-05-07` to `2026-05-09`.
- No Google Sheets writes.
- No live supplier contract writes.

Findings:
- Exact old shortcut profile `Chrome_UC136` / `BBPProfile` does not load the BBP extension panel in the probe; the profile has no BuyBotPro extension folder.
- `Chrome_UC136v2` / `BBPProfile1` loads the BBP iframe and can authenticate in normal mode.
- Automatic normal-mode BBP login works; BBP device deactivation was not needed.
- The dashboard Yes/No field can still show raw `LOGIN` after the authenticated BBP cost field is available. This was a false login-required block.
- A later Amazon review-page `blocked_or_signin_page` path was discarding already-collected BBP evidence.

Changed:
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
  - Treat raw dashboard `LOGIN` as non-blocking when the BBP cost field is already present.
  - Preserve already-collected BBP evidence when Amazon review capture returns `REVIEWS_TIMEOUT`.
- `scripts/flows/F/_scanner_state.py`
  - Treat the new authenticated-dashboard-missing log line as logged-in evidence.
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - Default BBP profile changed to `Chrome_UC136v2` / `BBPProfile1`.
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - Default child BBP profile changed to `Chrome_UC136v2` / `BBPProfile1`.
- `scripts/one_off/F063_run_f061_practice_list.py`
  - Added local no-Sheets practice runner for normal-mode F061 scrape proof.

Static proof:
- `python -m py_compile scripts\flows\F\F061_run_legacy_first_checks_local.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py scripts\flows\F\legacy_scanner_2_1\Webscrape.py scripts\flows\F\_scanner_state.py scripts\one_off\F063_run_f061_practice_list.py` passed.
- `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_f_scanner_state.py tests\test_f_legacy_webscrape_money_input.py -q` -> `111 passed`.

Runtime proof:
- One-row normal-mode proof before the fix reached BBP cost and sales fields but returned `BBP_LOGIN_REQUIRED` because dashboard Yes/No raw value was `LOGIN`.
- After the dashboard fix, the same row returned BBP data and failed only the business rule `LOWROI`.
- Isolated row 5 proof preserved BBP data even when Amazon reviews returned `blocked_or_signin_page`.
- Final 10-row practice proof: `out/systems/F/diagnostics/f061_practice_scrape_results_20260511T152407Z.json`.
- Final proof result: `scrape_data_count=10`, `login_required_count=0`, `failure_count=0`, `business_pass_count=0`.
- `business_pass_count=0` is expected for this practice list because the rows fail current business gates such as `LOWROI`; the browser scrape proof is the `scrape_data_count`.

Next proof gate:
- Trigger: resume FPM from maintenance and observe the first live F061 child with the new default profile.
- Artifact to inspect: `out/systems/F/price_list_manager/live/live_cycle_status.csv`, `out/systems/F/price_list_manager/live/f061_child_stderr.log`, and `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`.
- Success condition: FPM owner is running, child launch uses `Chrome_UC136v2` / `BBPProfile1`, and new live rows no longer fail as `BBP_LOGIN_REQUIRED` from the false dashboard `LOGIN` condition.
- Failure action: if live rows still fail BBP login, keep Login Mode paused and inspect the live child command line plus BBP iframe/login evidence before changing browser lifecycle again.

## Login Mode Phase 9P - Visible Hold Plan Matrix
Recorded UTC: 2026-05-11T15:46:19Z

User request:
- Work out 5 possible plans to fix the visible Login Mode browser problem, go through each one, and test it by holding the page open.

Maintenance boundary:
- FPM was paused through `out\locks\maintenance.requested` with `exit_after_drain=1` before the browser-hold matrix.
- No Google Sheets writes.
- No local DB alignment changes.

Plans tested:
- Plan 1: current F061-style `undetected_chromedriver` launch in visible mode.
- Plan 2: standard Selenium ChromeDriver launch in visible mode.
- Plan 3: raw Chrome launched from the script, then Selenium attaches to it.
- Plan 4: raw Chrome launched through Windows Explorer shell, then Selenium attaches to it.
- Plan 5: raw Chrome launched through a temporary interactive Scheduled Task, then Selenium attaches to it.

Result artifact:
- `out/systems/F/diagnostics/f064_visible_hold_plan_matrix_20260511T154007Z.json`
- `out/systems/F/diagnostics/f064_visible_hold_plan_matrix_20260511T154007Z.csv`

Matrix result:
- Plans 1 to 4 all launched Chrome, attached successfully, opened `https://www.amazon.co.uk/dp/B0046A3Z3O`, detected the BuyBotPro iframe, and detected authenticated BBP cost fields.
- Plans 1 to 4 all failed the Windows visibility proof: their specialist Chrome process had `main_window_handle=0`.
- Plan 5 launched the scheduled task path but Selenium could not attach, so it did not prove page load or visibility.
- In all successful page-load plans, BBP was authenticated and no BBP login form was present.

Root-cause conclusion:
- The BBP profile and normal scrape authentication are working with `Chrome_UC136v2` / `BBPProfile1`.
- The remaining failure is the Windows visible top-level window layer for Chrome launched from the Codex/tool context.
- Repeating standalone Chrome login attempts is not the fix. The Login Mode fix must keep using the normal script-owned F061 browser and must launch/hold it from a desktop/operator-visible context.

Diagnostic cleanup fix:
- `scripts/one_off/F064_run_visible_bbp_hold_plan_matrix.py` now counts only browser/driver processes for labelled hold tests.
- The cleanup now uses `taskkill /T /F` on labelled browser/driver process trees so Explorer-launched test Chrome children do not survive.

Cleanup proof:
- `python -m py_compile scripts\one_off\F064_run_visible_bbp_hold_plan_matrix.py` passed.
- Short cleanup regression: `out/systems/F/diagnostics/f064_visible_hold_plan_matrix_20260511T154545Z.json`.
- The regression opened the same page and BBP panel, still had `visible_window=false`, and left `remaining_processes_after_cleanup=[]`.

Post-test ownership restoration:
- Removed `out\locks\maintenance.requested` and `out\locks\maintenance.ready`.
- Restarted scheduled task `AMZ Price List Manager`.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` recorded new owner `pid=7840`, state `running`, run `fpm_live_20260511T154657Z`, active supplier `stax`, pending rows `20646`.
- `out/systems/F/price_list_manager/live/f061_child_status.txt` recorded normal child `pid=14188`, `browser_mode=minimized`, `browser_visibility=hidden`, heartbeat `2026-05-11T15:47:49Z`.
- `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt` recorded `auth_state=LOGGED_IN`.

Next proof gate:
- Trigger: after FPM ownership is restored, build or run a desktop/operator-launched visible normal F061 hold proof from the logged-in Windows desktop context, not from a standalone maintenance browser.
- Artifact to inspect: the visible-hold proof artifact under `out/systems/F/diagnostics/`, plus `out/systems/F/price_list_manager/live/f061_child_stderr.log` if it is routed through FPM.
- Success condition: the normal F061 child uses `Chrome_UC136v2` / `BBPProfile1`, opens the same Amazon/BBP page, and Windows reports a visible top-level Chrome window while the page is held open.
- Failure action: if the desktop/operator-launched normal F061 hold is also invisible, stop changing scanner logic and inspect Windows desktop/session/window-manager state before making another Login Mode change.

## Normal Scanner Phase 9Q - Hidden Normal BBP Proof
Recorded UTC: 2026-05-11T15:59:45Z

User correction:
- Forget Login Mode for now; the normal scanner is the priority.

Live state before proof:
- FPM was running and processing normal Stax chunks.
- Pending rows moved from `20646` to `20631`.
- Recent normal chunks mostly did not attempt browser scraping because rows failed earlier as `ROIFAIL`, `OVER50K`, or `NOASIN`.
- The most recent live browser-attempted rows before the profile fix were parked as `LOGIN_BACKTRACK` with `No BBP iframe`.

Diagnostic change:
- `scripts/one_off/F063_run_f061_practice_list.py` now accepts `--browser-mode visible|minimized`.
- `--browser-mode minimized` sets the same hidden normal-mode environment used by FPM:
  - `F061_BACKGROUND_BROWSER_MODE=minimized`
  - `F061_SHOW_WINDOWS=0`
  - `FPM_LIVE_HIDE_SCRAPER_WINDOWS=1`

No-Sheets hidden proof:
- FPM was paused through `out\locks\maintenance.requested` and drained to `drain_exit`.
- Practice input: `out/systems/F/diagnostics/f061_recent_no_bbp_iframe_practice_list_20260511T155300Z.csv`.
- Input rows were the three recent live rows that failed with `No BBP iframe`:
  - `B017MDL1B4`
  - `B0DBQ3F3R1`
  - `B0DWXY4SPD`
- Command proof used hidden/minimized normal mode, not Login Mode.
- Result artifact: `out/systems/F/diagnostics/f061_practice_scrape_results_20260511T155706Z.json`.
- Result: `scrape_data_count=3`, `login_required_count=0`, `failure_count=0`, `business_pass_count=0`.
- `business_pass_count=0` is not a browser failure; the three rows produced BBP scrape data and then failed later business/review rules.

Important finding:
- Normal hidden BBP scraping now works in isolated proof for the same ASINs that live previously parked as `No BBP iframe`.
- The live loop has not yet hit another browser-scrape candidate after this proof; current live chunks are failing earlier gates.

Post-test ownership restoration:
- Cleared maintenance locks.
- Restarted scheduled task `AMZ Price List Manager`.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` recorded new owner `pid=29440`, state `running`, active supplier `stax`, pending rows `20631`.
- `out/systems/F/price_list_manager/live/f061_child_status.txt` recorded normal child `pid=31084`, `browser_mode=minimized`, `browser_visibility=hidden`.

Next proof gate:
- Trigger: next live F061 chunk that records `scrape_attempted_rows > 0`.
- Artifact to inspect: `out/systems/F/price_list_manager/live/f061_child_stdout.log`, `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`, and `out/systems/F/live/f_login_backtrack_evidence_live.csv`.
- Success condition: live scrape-attempted row records BBP scrape data or fails only a later business/review rule, not `No BBP iframe` or `BBP_LOGIN_REQUIRED`.
- Failure action: if a new live row still parks as `No BBP iframe`, compare the live child environment and Chrome command line against the hidden proof artifact before changing scanner logic again.

## Normal Scanner Phase 9R - Hidden Proof Rerun
Recorded UTC: 2026-05-11T16:12:17Z

User request:
- Run the normal hidden proof again.

Action:
- Paused FPM through `out\locks\maintenance.requested`.
- Waited for maintenance boundary.
- Reran the same no-Sheets, minimized normal-mode practice list:
  - `out/systems/F/diagnostics/f061_recent_no_bbp_iframe_practice_list_20260511T155300Z.csv`

Result artifact:
- `out/systems/F/diagnostics/f061_practice_scrape_results_20260511T160832Z.json`

Result:
- `scrape_data_count=3`
- `login_required_count=0`
- `failure_count=0`
- `business_pass_count=0`

Evidence:
- All 3 rows found the BBP iframe/container.
- All 3 rows logged `BBP login skipped: already authenticated`.
- All 3 rows logged `Dashboard yes/no raw LOGIN ignored after authenticated cost field; treating dashboard as missing`.
- No row failed with `No BBP iframe`.
- No row failed with `BBP_LOGIN_REQUIRED`.

Post-test ownership restoration:
- Cleared maintenance locks.
- Restarted scheduled task `AMZ Price List Manager`.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` recorded new owner `pid=11120`, state `running`, active supplier `stax`, pending rows `20601`.
- `out/systems/F/price_list_manager/live/f061_child_status.txt` recorded normal child `pid=29508`, `browser_mode=minimized`, `browser_visibility=hidden`.

Current interpretation:
- Normal hidden BBP scraping is now proven twice in isolated mode for the exact recent live `No BBP iframe` ASINs.
- The remaining live proof is waiting for the next live chunk that actually reaches browser scraping.

## Normal Scanner Phase 9S - Chrlauncher Update/Visibility Check
Recorded UTC: 2026-05-11T16:20:23Z

User evidence:
- Operator reported that opening the browser kept trying to update and was intentionally not updated because the old browser formatting mattered.
- Operator is on phone and cannot manually double-click the desktop launcher now.

Findings:
- `C:\Chrome_UC136\bin\chrome.exe` is still Chrome `136.0.7103.114`, last modified `2025-05-28`.
- `C:\Chrome_UC136v2\bin\chrome.exe` is Chrome `148.0.7778.97`, last modified `2026-05-11T15:52:32Z`, so an update did occur on the v2 launcher tree.
- `C:\Chrome_UC136v2\chrlauncher.ini` was pointing at the old profile path `C:\Users\Luke\AppData\Local\Chrome_UC136` / `BBPProfile`.
- Both chrlauncher configs were set to check for updates every 2 days and to wait for update/download before opening Chrome.

Action:
- Backed up:
  - `C:\Chrome_UC136\chrlauncher.ini.sellerone_backup_20260511T161930Z`
  - `C:\Chrome_UC136v2\chrlauncher.ini.sellerone_backup_20260511T161930Z`
- Updated both launcher configs:
  - `ChromiumCommandLine=--user-data-dir="C:\Users\Luke\AppData\Local\Chrome_UC136v2" --profile-directory="BBPProfile1" --no-default-browser-check`
  - `ChromiumAutoDownload=false`
  - `ChromiumBringToFront=false`
  - `ChromiumWaitForDownloadEnd=false`
  - `ChromiumCheckPeriod=0`
- Stopped the stray `chrlauncher 2.6` process.

Launch check:
- Started `C:\Chrome_UC136\chrlauncher 2.6 (64-bit).exe`.
- It launched stable Chrome 136 directly:
  - `C:\Chrome_UC136\bin\chrome.exe`
  - `--user-data-dir="C:\Users\Luke\AppData\Local\Chrome_UC136v2"`
  - `--profile-directory="BBPProfile1"`
- No updater process remained active.

Remaining problem:
- Even after launching through the Explorer desktop shell, Windows still reported `MainWindowHandle=0` from the remote Codex context.
- This means the update/profile issue was real, but it does not by itself solve the "visible window from remote tool launch" problem.

Post-test ownership restoration:
- Stopped the launcher test Chrome tree.
- Cleared maintenance locks.
- Restarted scheduled task `AMZ Price List Manager`.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` recorded owner `pid=11492`, state `running`, pending rows `20596`.
- `out/systems/F/price_list_manager/live/f061_child_status.txt` recorded child `pid=31224`, `browser_mode=minimized`, `browser_visibility=hidden`.

Next proof gate:
- Trigger: operator is physically at the PC or connected through Chrome Remote Desktop and can interact with the real desktop.
- Action: open `C:\Chrome_UC136\chrlauncher 2.6 (64-bit).exe` or the scanner visible-hold launcher and confirm whether Chrome appears without an update prompt.
- Success condition: visible Chrome opens as Chrome 136 using `Chrome_UC136v2` / `BBPProfile1` and BBP is present.
- Failure action: if Chrome still does not appear when the operator is actually on the desktop, inspect Windows display/session state rather than scanner code.

## Normal Scanner Phase 9T - Direct Launcher and Old Scanner Alignment
Recorded UTC: 2026-05-11T16:41:12Z

User evidence:
- Operator reported Chrome was opening/updating/crashing and the normal scanner browser had not been visibly reliable for days.
- Operator asked to compare with `C:\Users\Luke\Desktop\Price List Manager.lnk`, which launches the old scanner folder.

Action:
- Added direct frozen-browser launcher:
  - `run_BBP_chrome_136_direct.bat`
  - Uses `C:\Chrome_UC136\bin\chrome.exe`
  - Uses `C:\Users\Luke\AppData\Local\Chrome_UC136v2`
  - Uses `BBPProfile1`
  - Bypasses chrlauncher update behavior.
- Updated old desktop scanner file:
  - `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1\firstCheck.py`
  - Backup: `C:\Users\Luke\Desktop\Amazon Price List Scanner 2.1\firstCheck.py.sellerone_backup_20260511T163543Z`
  - Now launches stable Chrome 136 with the same `Chrome_UC136v2` / `BBPProfile1` BBP profile used by the restored SellerOne scanner path.
- Updated repo scanner file:
  - `scripts/flows/F/legacy_scanner_2_1/firstCheck.py`
  - Same stable Chrome/profile alignment.

Static proof:
- `py_compile` passed for the old desktop scanner `firstCheck.py`.
- `py_compile` passed for the repo scanner `firstCheck.py`.

Live proof after restore:
- Login Mode request is absent.
- Maintenance locks are clear.
- `out/systems/F/price_list_manager/live/live_cycle.lock` records owner `pid=4268`, `owner=FPM130_live_cycle`.
- `out/systems/F/price_list_manager/live/live_cycle_status.csv` recorded post-restore successful F061 chunks:
  - `2026-05-11T16:38:38Z`, pending moved to `20527`, `scrape_failed_rows=0`, `scanner_speed_browser_blocked_rows=0`
  - `2026-05-11T16:39:57Z`, pending moved to `20522`, `scrape_failed_rows=0`, `scanner_speed_browser_blocked_rows=0`
  - `2026-05-11T16:41:18Z`, pending moved to `20517`, `scrape_failed_rows=0`, `scanner_speed_browser_blocked_rows=0`
  - `2026-05-11T16:42:05Z`, pending moved to `20512`, `scrape_failed_rows=0`, `scanner_speed_browser_blocked_rows=0`
- `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt` records `auth_state=LOGGED_IN`, `browser_state=HIDDEN`.

Known older evidence:
- One pre-alignment live browser row hit `No BBP iframe` at `2026-05-11T16:25:31Z` for ASIN `B0051HED3W`.
- Treat this as old evidence unless it repeats after the direct launcher/profile alignment.

Next proof gate:
- Trigger: next live F061 chunk with `scrape_attempted_rows > 0` after `2026-05-11T16:41:12Z`.
- Artifacts to inspect:
  - `out/systems/F/price_list_manager/live/f061_child_stdout.log`
  - `out/systems/F/price_list_manager/live/f061_child_stderr.log`
  - `out/systems/F/live/feeder_legacy_scrape_evidence_live.csv`
  - `out/systems/F/live/f_login_backtrack_evidence_live.csv`
- Success condition: no new `No BBP iframe` or `BBP_LOGIN_REQUIRED`; scrape row either records BBP evidence or fails only a later business/review rule.
- Failure action: if a new post-alignment live row hits `No BBP iframe`, pause FPM at a maintenance boundary and run the same ASIN through `F063_run_f061_practice_list.py --browser-mode visible --final-hold-seconds 900` before changing scanner logic.

Monitoring approval:
- Approved by operator message `monitor`.
- Cadence: poll live FPM/F061 artifacts every 60 seconds.
- Stop condition: first post-alignment chunk with `scrape_attempted_rows > 0`, or a new post-alignment `No BBP iframe` / `BBP_LOGIN_REQUIRED`, or 60 minutes without a scrape-attempted row.
- Timeout action: record `parked pending next proof window` with the latest pending count and next trigger.

## Login Mode Phase 9R - Chrome Launch And BBP Profile Repair
Recorded UTC: 2026-05-12T10:50:00Z

User request:
- Investigate why the repricer/F061 browser is not staying open for the operator to log everything in again after a Chrome update.

Findings:
- `C:\Chrome_UC136\bin\chrome.exe` is still stable Chromium `136.0.7103.114`.
- `C:\Chrome_UC136v2\bin\chrome.exe` is now Chromium `148.0.7778.97`, modified on `2026-05-11`, so a browser update did happen on the v2 launcher tree.
- The scanner ChromeDriver is still pinned to version 136, so F061 should not use the Chrome 148 executable unless a matching driver path is introduced and tested.
- The old current defaults `Chrome_UC136v2` / `BBPProfile1` no longer contain the BuyBotPro extension.
- `Chrome_UC136` / `Profile 2` was the only specialist Chromium profile found with the BuyBotPro extension marker before the manual launch test, but after opening it through Chrome 136 the extension folder was absent and FPM160 reported `bbp_extension_ok=0`.
- Google Chrome user profiles still have the BuyBotPro extension, but those are not the current F061 pinned Chromium 136 automation profiles.

Changed:
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - Default BBP user data/profile changed to `C:\Users\Luke\AppData\Local\Chrome_UC136` / `Profile 2`.
  - Added driver launch timing logs: profile health, Chrome exe/version, launch attempt, ready elapsed seconds, debugger address, date-driver timing, and launch failure elapsed seconds.
- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - Default child BBP profile changed to `Chrome_UC136` / `Profile 2`.
  - Child stdout now records BBP user-data/profile and F061 elapsed runtime.
- `scripts/flows/F/price_list_manager/FPM160_f061_visible_login_maintenance.py`
  - Default visible-login browser changed to Chrome 136 with `Chrome_UC136` / `Profile 2`.
  - Added Chrome version, BBP extension health, launch timing, process snapshot, alive-after-verify, and visible-window proof.
  - Latest launch status is written to `out/systems/F/diagnostics/fpm160_visible_login_launch_status.json`.
- `scripts/one_off/F063_run_f061_practice_list.py`, `scripts/one_off/F064_run_visible_bbp_hold_plan_matrix.py`, and `run_BBP_chrome_136_direct.bat`
  - Defaults changed to the same Chrome 136 / `Profile 2` path.

Proof:
- Static compile passed for F061, FPM130, FPM160, F063, and F064.
- Focused tests passed: `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_fpm160_visible_login_maintenance.py -q` -> `93 passed`.
- Short F064 launch probe after the change: `out/systems/F/diagnostics/f064_visible_hold_plan_matrix_20260512T104313Z.json`.
  - Chrome launched and stayed visible for both tested plans.
  - BBP panel was not detected.
- FPM160 live visible-login launch proof: `out/systems/F/diagnostics/fpm160_visible_login_launch_status.json`.
  - `chrome_version=136.0.7103.114`
  - `user_data_dir=C:\Users\Luke\AppData\Local\Chrome_UC136`
  - `profile_dir=Profile 2`
  - `alive_after_verify=true`
  - `visible_window=true`
  - `bbp_extension_ok=0`

Root-cause conclusion:
- The Chrome window can now be launched and kept open.
- The remaining blocker is not the browser lifecycle. The F061 automation profile is missing the BuyBotPro extension/session state, so the user cannot complete a useful BBP login until the extension is installed/enabled in the same Chrome 136 profile F061 will use.

Next proof gate:
- Trigger: after the operator installs/enables BuyBotPro and logs into Amazon/BBP in the currently opened Chrome 136 `Profile 2` window.
- Artifact to inspect: `out/systems/F/diagnostics/fpm160_visible_login_launch_status.json`, `out/systems/F/diagnostics/f064_visible_hold_plan_matrix_*.json`, and a one-row F063 practice result.
- Success condition: `bbp_extension_ok=1`, F064 detects the BBP iframe/login or authenticated cost fields, and F063 no-Sheets practice returns BBP scrape data rather than `BBP_LOGIN_REQUIRED`.
- Failure action: do not resume live FPM row burning. Inspect extension installation state first, then either reinstall BuyBotPro in `Chrome_UC136` / `Profile 2` or plan a Chrome 148 + matching ChromeDriver migration.

## Login Mode Phase 9S - Operator Launch Mode Correction
Recorded UTC: 2026-05-12T10:57:53Z

User correction:
- The first plain visible launch opened the expected profile and allowed BBP login.
- A later diagnostic/automation-style launch opened what looked like the same profile, but the BBP account showed `verify` instead of the logged-in account.
- Treat the Chrome profile path as probably correct and the launch method as an authentication-state risk.

Changed interpretation:
- The Phase 9R conclusion that the profile itself was missing the useful BBP state is too strong.
- File-system extension checks are only supporting evidence; they do not prove the runtime BBP account state seen by the operator.
- Do not run repeated UC/Selenium/diagnostic launches while the operator is trying to restore login.

Changed launcher behavior:
- `FPM160_f061_visible_login_maintenance.py` now uses a plain Windows `cmd /c start` launch with only:
  - `C:\Chrome_UC136\bin\chrome.exe`
  - `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136`
  - `--profile-directory=Profile 2`
  - the Amazon product URL
- It no longer adds `--new-window`, `--no-first-run`, `--no-default-browser-check`, or Selenium/remote-debugging flags.
- If a matching Chrome 136 / `Chrome_UC136` / `Profile 2` window is already open, FPM160 records `already_open` and does not launch a second browser.

Current proof:
- Latest root browser process: PID `20884`.
- Command line: `C:\Chrome_UC136\bin\chrome.exe --user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136 "--profile-directory=Profile 2" https://www.amazon.co.uk/dp/B07BZ3L76B`.
- No remote-debugging, Selenium, `--test-type`, or `--no-sandbox` flags are present on the root process.
- FPM remains drained with `F_restart_drain.ready` and `f061_visible_login.requested` present.

Next proof gate:
- Wait for the operator to finish logging into BBP/Amazon in the existing PID `20884` window.
- After confirmation, run only one controlled no-Sheets F061/F063 proof to see whether the actual scanner launch preserves the login or causes the `verify` account state.
- Keep live FPM drained until that proof shows the scanner can see the authenticated BBP state.

## Login Mode Phase 9T - BuyBotPro Extension Package Repair
Recorded UTC: 2026-05-12T11:07:37Z

User correction:
- The visible browser that was open was still wrong: BuyBotPro showed `The extension failed to load properly. It might not be able to intercept network requests.`

Findings:
- Active scanner profile `C:\Users\Luke\AppData\Local\Chrome_UC136\Profile 2` had a BuyBotPro preference entry for extension ID `docdmgijbdlobilamkipaleciekbgbgl`, version `1.15.88`.
- The active scanner profile was missing the matching extension package folder:
  - `C:\Users\Luke\AppData\Local\Chrome_UC136\Profile 2\Extensions\docdmgijbdlobilamkipaleciekbgbgl`
- This left the profile in a half-installed/corrupt state: Chrome thought BuyBotPro existed, but the extension files were absent.
- Normal Google Chrome `Profile 1` had a readable BuyBotPro `1.15.88` package.
- The same-profile backup under `Chrome_UC136.CHROME_DELETE` also had the extension folder, but its version directory was not readable due access denied.

Repair:
- Copied only the BuyBotPro extension package from:
  - `C:\Users\Luke\AppData\Local\Google\Chrome\User Data\Profile 1\Extensions\docdmgijbdlobilamkipaleciekbgbgl`
- To the scanner profile:
  - `C:\Users\Luke\AppData\Local\Chrome_UC136\Profile 2\Extensions\docdmgijbdlobilamkipaleciekbgbgl`
- Did not copy BBP local extension settings, tokens, or credentials.

Proof:
- Target BuyBotPro manifest hash matches the source manifest hash.
- Target extension package contains 30 files.
- New visible scanner launch proof:
  - `out/systems/F/diagnostics/fpm160_visible_login_launch_status.json`
  - `chrome_version=136.0.7103.114`
  - `user_data_dir=C:\Users\Luke\AppData\Local\Chrome_UC136`
  - `profile_dir=Profile 2`
  - `bbp_extension_ok=1`
  - `alive_after_verify=true`
  - `visible_window=true`
- Root Chromium process after repair: PID `25536`.

Next proof gate:
- Operator should check the visible Chromium PID `25536` window and confirm whether the BuyBotPro load/intercept warning is gone.
- If the warning is gone, log into BBP/Amazon there, then run one controlled no-Sheets F061/F063 proof.
- If the warning remains, inspect Chrome extension details/errors for `docdmgijbdlobilamkipaleciekbgbgl` before running any scanner proof.

## Login Mode Phase 9U - Scanner Conditions Auth Proof
Recorded UTC: 2026-05-12T11:14:24Z

User state:
- Operator confirmed BBP and Amazon were logged in and asked to test under price-list scanner conditions.

Pre-proof handling:
- Closed only the plain visible Chromium 136 login window so the scanner could take the `Chrome_UC136` profile lock cleanly.
- Live FPM remained drained; no live queue rows were resumed or burned.

First proof attempt:
- Command: `python scripts\one_off\F063_run_f061_practice_list.py --limit 1 --browser-mode visible --login-hold-seconds 20 --page-load-timeout-seconds 60 --row-pause-seconds 0 --final-hold-seconds 0 --stop-after-login-required`
- It exposed a code bug in the new launch timing logs: `NameError: name 'logger' is not defined`.
- Fix: added a standard module logger in `scripts\flows\F\F061_run_legacy_first_checks_local.py`.

Successful scanner proof:
- Same F063 command rerun at `2026-05-12T11:12:48Z`.
- Input row: ASIN `B0046A3Z3O`, supplier SKU `1019`.
- Browser launch was the real scanner shape:
  - `C:\Chrome_UC136\bin\chrome.exe`
  - `--user-data-dir=C:\Users\Luke\AppData\Local\Chrome_UC136`
  - `--profile-directory=Profile 2`
  - ChromeDriver/UC automation flags including remote debugging and test type.
- Launch timing proof:
  - `F061_BBP_PROFILE_HEALTH ok=True reason=buybotpro_extension_found`
  - `F061_BBP_DRIVER_READY elapsed_seconds=1.078 debugger_address=127.0.0.1:56233`
  - `F061_DATE_DRIVER_READY elapsed_seconds=4.469`
- Auth proof:
  - `BBP iframe/container detected after refresh`
  - `Found BBP iframe`
  - `BBP login skipped: already authenticated`
- Data proof:
  - `bbp_final_sell_price=10.58`
  - `bbp_sales_chart_source=estSalesMonthlyChart:chartjs`
  - `scrape_data_available=True`
  - `login_required_count=0`
- Business outcome:
  - Row failed as `LOWROI`, which is a normal business-rule result and not an auth/browser failure.

Artifacts:
- `out/systems/F/diagnostics/f061_practice_scrape_results_20260512T111248Z.json`
- `out/systems/F/diagnostics/f061_practice_scrape_results_20260512T111248Z.csv`
- `out/systems/F/diagnostics/f063_scanner_conditions_20260512T111248Z.err.log`
- Legacy webscrape log: `scripts/flows/F/legacy_scanner_2_1/logs/webscrape_20260512_121250.log`

Verification:
- Static compile passed for F061 and F063 after the logger fix.
- Focused tests passed: `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm160_visible_login_maintenance.py -q` -> `54 passed`.
- Pytest emitted a Windows temp cleanup `PermissionError` after success; exit code remained 0.

Next gate:
- Scanner conditions are now authenticated for a one-row no-Sheets proof.
- If resuming live FPM, keep the repaired Chrome 136 / `Profile 2` defaults and monitor the first live chunk for new `BBP_LOGIN_REQUIRED`, `No BBP iframe`, or extension-load warnings.

## Login Mode Phase 9V - LIKELY Dashboard Signal And Backtrack Proof
Recorded UTC: 2026-05-12T11:42:23Z

User finding:
- BuyBotPro can show `LIKELY` in the dashboard Yes/No/Login position.
- Operational meaning: sellable hazmat/separate-delivery signal, not missing evidence.

Implementation:
- `LIKELY` is now a first-class dashboard signal, while `YES` and `NO` remain the binary dashboard values.
- Scanner output now carries:
  - `bbp_dashboard_yes_or_no=LIKELY`
  - `bbp_dashboard_delivery_classification=LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY`
  - `bbp_dashboard_separate_delivery_required=1`
- F061 no longer parks `LIKELY` rows as `dashboard_yes_no_backtrack_required`.
- Blank/missing dashboard values still go to `login_backtrack_pending`.
- `LOGIN` still triggers visible-login/backtrack handling.
- Review-pack and triage outputs carry matching `seller_history_dashboard_*` fields so the operator can see the separate-delivery flag after review pack build.

Backtrack behavior:
- Login-required rows still rank before dashboard-missing backtrack rows.
- Dashboard-missing rows still rank before normal pending rows in login mode.
- `LIKELY` rows are not part of the incomplete/dashboard-missing backlog.

Verification:
- Static compile passed for the edited scanner, review-pack, triage, and practice scripts.
- Expanded regression command:
  - `python -m pytest tests\test_f_scanner_state.py tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_f090_build_amazon_listing_intake.py tests\test_f019_build_live_price_file_near_miss_pack.py tests\test_f021_build_new_product_review_fail_triage.py tests\test_f028_build_dashboard_yes_no_rescan_plan.py tests\test_f_legacy_webscrape_money_input.py -q`
- Result: `188 passed`.
- Pytest emitted the known Windows temp cleanup `PermissionError` after success; exit code remained 0.

Scanner-conditions proof:
- Command:
  - `python scripts\one_off\F063_run_f061_practice_list.py --limit 1 --browser-mode visible --login-hold-seconds 20 --page-load-timeout-seconds 60 --row-pause-seconds 0 --final-hold-seconds 0 --stop-after-login-required`
- Output:
  - `out/systems/F/diagnostics/f061_practice_scrape_results_20260512T114036Z.csv`
  - `out/systems/F/diagnostics/f061_practice_scrape_results_20260512T114036Z.json`
  - `scripts/flows/F/legacy_scanner_2_1/logs/webscrape_20260512_124038.log`
- Proof values:
  - `F061_BBP_PROFILE_HEALTH ok=True reason=buybotpro_extension_found`
  - `F061_BBP_DRIVER_READY elapsed_seconds=1.000`
  - `BBP login skipped: already authenticated`
  - `Dashboard yes/no => LIKELY; delivery_classification=LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY`
  - `login_required_count=0`
  - `scrape_data_count=1`
  - CSV row: `dashboard_yes_no=LIKELY`, `dashboard_delivery_classification=LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY`, `dashboard_separate_delivery_required=1`
- Business outcome remained `LOWROI`, which is expected and unrelated to auth/browser/backtrack handling.

Next gate:
- Safe to resume a small live FPM chunk when ready.
- Monitor the first chunk for:
  - `BBP_LOGIN_REQUIRED`
  - `dashboard_yes_no_backtrack_required`
  - `dashboard_yes_no=LIKELY`
  - `seller_history_dashboard_delivery_classification=LIKELY_SELLABLE_HAZMAT_SEPARATE_DELIVERY`

## Login Mode Phase 9W - Live Resume And 20 Minute Monitor
Recorded UTC: 2026-05-12T12:27:23Z

Actions:
- Cleared visible-login maintenance/drain markers with `FPM160_f061_visible_login_maintenance.py clear`.
- Restarted normal live price-list manager with `run_F_price_list_manager_cycle.bat`.
- Active FPM owner after restart: PID `25428`, run `fpm_live_20260512T120429Z`, supplier `stax`, scanner run `fpm_stax_20260507T151124Z`.
- Requested login-recovery mode for the existing incomplete BBP backlog via `request_price_list_login_mode_from_ui(...)`.

20-minute monitor result:
- FPM stayed running and responsive.
- Chrome/BBP stayed authenticated under price-list scanner conditions.
- Current child status at local 13:27:23: `browser_mode=visible`, `browser_visibility=hidden`, heartbeat `2026-05-12T12:27:04Z`.
- No current `BBP_LOGIN_REQUIRED`, `No BBP iframe`, extension-load warning, or `failed to load` error appeared during the monitored window.
- Logs repeatedly showed:
  - `BBP iframe/container detected after refresh`
  - `Found BBP iframe`
  - `BBP login skipped: already authenticated`
  - dashboard values being read normally (`Dashboard yes/no => NO` in the latest monitored rows)

Backtrack progress:
- Existing BBP login/backtrack backlog started at `78` rows.
- Login-mode cycles completed and merged rows while the normal live manager remained active:
  - 12:06Z: selected 5, merged 4, backlog `73`
  - 12:12Z: selected 5, merged 4, backlog `68`
  - 12:17Z: selected 5, merged 4, backlog `63`
  - 12:21Z: selected 5, merged 5, backlog `58`
- Normal FPM pending rows moved from `20443` at resume to `20413` at the final monitor check.

Operational state:
- The normal live process is resumed.
- Login-recovery remains active because `58` backtrack rows still remain.
- Once the backtrack queue drains, FPM should continue normal pending-row processing.

## Login Mode Phase 9X - DHB Targeted Dashboard Recovery Setup And Hider Fix
Recorded UTC: 2026-05-12T12:39:42Z

DHB check:
- Full DHB rerun is not required based on current evidence.
- DHB scan memory has no Chrome/auth/BBP iframe failure bucket.
- Two DHB rows still need targeted dashboard Yes/No recovery:
  - `OB401` / `B094VK1733` / candidate `cf439f1080699fcf237fb7045d068f358e27c519`
  - `PIK065` / `B07J9JGZZV` / candidate `8e9fb042d35b72dafb3bf5ce702fbaf64fcca460`
- Target file prepared:
  - `out/systems/F/price_list_manager/recovery_targets/dhb_dashboard_backtrack_targets_20260512T123942Z.csv`
- Runbook prepared:
  - `out/systems/F/price_list_manager/recovery_targets/dhb_dashboard_backtrack_runbook_20260512T123942Z.md`

Operational guard:
- Current live FPM is processing `stax`, so the DHB target was prepared but not run concurrently against the same BBP Chrome profile.
- Run the DHB two-row recovery once the scanner is idle/paused/drained, then rebuild the DHB review pack.

Browser visibility fix:
- Root cause for visible browser after BBP login: `f_hide_scraper_windows.ps1` skipped hiding while Login Mode request status was `holding` or `authenticated_backlog_remaining`, even after `f061_browser_visibility_state.txt` said `state=hidden|auth_state=LOGGED_IN`.
- Patch: the hider now obeys the hidden/logged-in visibility state even if Login Mode remains active for backlog processing.
- Restarted the hider helper.
- Proof:
  - PowerShell scriptblock parse passed for `scripts/tools/f_hide_scraper_windows.ps1`.
  - Windows visible-window enumeration showed only normal Google Chrome visible (`ChatGPT - Chef - Google Chrome`), with no visible `Chrome_UC136` or `Chrome_91_F061` scanner window.

## Login Mode Phase 9Y - Treat BBP Unavailable As Incomplete Backtrack
Recorded UTC: 2026-05-12T12:45:00Z

User question:
- If scraping errors because BBP is unavailable, it should be treated as incomplete/backtrack, similar to `LOGIN`, not as a final business failure.

Implementation:
- Existing handling already parked `BBP_LOGIN_REQUIRED`, `No BBP iframe`, and `BuyBotPro error` as `login_backtrack_pending`.
- Extended the BBP unavailable classifier to also park extension/intercept/load failures, including:
  - `BBP unavailable`
  - `BuyBotPro unavailable`
  - `BBP iframe preflight failed`
  - `extension failed`
  - `extension failed to load`
  - `failed to load properly`
  - `intercept network requests`
  - `BBP extension`
- These rows now get:
  - `scan_status=login_backtrack_pending`
  - `scan_reason=login_backtrack_required`
  - `completion_block_reason=bbp_login_required`
  - ledger `backtrack_status=blocked_login`

Verification:
- Added focused regression for the exact extension/intercept error class.
- `python -m pytest tests\test_f061_run_legacy_first_checks_local.py -q` -> `51 passed`.
- Pytest emitted the known Windows temp cleanup `PermissionError` after success; exit code remained 0.

## Login Mode Phase 9Z - Cross-Supplier Completed-Run Backtrack Recovery
Recorded UTC: 2026-05-12T13:02:00Z

User requirement:
- If a price list finishes with BBP/Login/dashboard data missing, those rows must not be stranded.
- When BBP is later logged in during another supplier run, the manager should bring back the missing rows from finished price lists and scan them before continuing normal pending rows.

Implementation:
- FPM130 now promotes unmerged rows from `f_login_backtrack_evidence_live.csv` back into `supplier_price_list_active_run.csv` when:
  - Login Mode is active, and
  - saved browser state is logged in/hidden.
- Promoted rows are restored as:
  - `scan_status=login_backtrack_pending`
  - `scan_reason=login_backtrack_required`
  - `completion_block_reason=bbp_login_required` or `dashboard_yes_no_backtrack_required`
- F061 now preserves other suppliers' active rows, run states, screening state, first-check rows, scrape evidence, and chart rows while scanning one supplier. This is required so a DHB recovery row is not overwritten by a Stax chunk, or vice versa.

Verification:
- Focused regression command:
  - `python -m pytest tests\test_f061_run_legacy_first_checks_local.py tests\test_fpm130_live_cycle.py tests\test_fpm140_review_handoff_ready.py -q`
- Result: `98 passed`.
- Existing single-supplier overwrite regression was updated to assert the new required behavior: current supplier is rewritten while other supplier rows are preserved.
- Pytest emitted the known Windows temp cleanup `PermissionError` after success; exit code remained 0.

Live reload and proof:
- Requested clean FPM reload with `action=reload` / `exit_after_drain=1`.
- Old owner `25428` reached `drain_exit` at `2026-05-12T12:58:50Z`.
- Restarted normal live manager; new owner `26728`.
- New owner promoted `20` unmerged backtrack rows from completed/blocked history:
  - suppliers: `dhb`, `entertainment_trading`, `stax`
- Active queue proof after first new-code chunk:
  - Stax `bbp_login_required` backtrack rows reduced from `48` to `43`.
  - DHB recovery rows remain active and preserved:
    - `OB401` / candidate `cf439f1080699fcf237fb7045d068f358e27c519`
    - `PIK065` / candidate `8e9fb042d35b72dafb3bf5ce702fbaf64fcca460`
- These recovery rows are ahead of normal Stax pending rows, so they will be handled before the manager marches on through ordinary pending stock.
