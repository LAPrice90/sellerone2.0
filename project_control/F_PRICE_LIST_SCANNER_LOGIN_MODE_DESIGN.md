# F Price List Scanner Login Mode Design

Created UTC: 2026-05-09T11:05:00Z

## Purpose
Give the operator a clear, controlled way to recover BBP/Amazon login without stopping the price-list scanner or opening the wrong Chrome window.

The scanner must keep doing non-browser work overnight. Rows that need BBP login must be stored as login work, shown in the Price List Queue UI, and replayed only after the operator presses a Login button.

## Current Root Cause
The scanner has two different kinds of work:
- API/catalog work that can continue without BBP login.
- BBP browser work that needs an authenticated BuyBotPro/Amazon session.

When BBP login is missing, the current F061 path correctly parks affected rows as `login_backtrack_pending`, but the UI does not yet expose this as a proper operator lane and the runtime does not yet have a clean operator-triggered Login Mode.

## Operator Story
Example:
- At 02:00, BBP is logged out.
- The scanner keeps running the price list.
- Rows that do not need BBP login continue normally.
- Rows that need BBP login are stored as `login_backtrack_pending`.
- At 09:15, the operator opens the Price List Queue UI.
- The active scanner card shows counts in this order:
  - PASS
  - FAIL
  - LOGIN
  - RE SCAN
- The Login button is red when login rows exist or auth evidence says login is required.
- The Login button is grey/disabled when there are no login rows and auth evidence says logged in.
- The operator presses Login.
- The next normal F061 child enters Login Mode, opens the first login-required ASIN from the parked queue in the normal script-owned F061 Chrome profile, and stays hidden unless a real Amazon/BBP login option is detected.
- If a real login option is detected, F061 surfaces that same scanner-owned browser once, waits for the operator hold window, then refreshes/rechecks login evidence.
- Once login evidence is clean, F061 works through the parked login rows first.
- When login rows reach 0, F061 returns to normal queue order.

## Hard Rules
- Do not open a separate standalone Chrome login window.
- Do not use `FPM160_f061_visible_login_maintenance.py open` for this flow.
- The browser must be the normal F061 child browser.
- The browser must use the same profile as the normal legacy scanner: `Chrome_UC136` / `BBPProfile`.
- The login flow must not change Google Sheets.
- Login rows must stay in the local F active queue until properly replayed or explicitly parked.
- Review handoff must remain blocked while `login_backtrack_pending` rows exist.

## Data Model
Use the existing active-run and backtrack contracts first.

Existing source of truth:
- `out/systems/F/inbox/supplier_price_list_active_run.csv`
  - `scan_status=login_backtrack_pending`
  - `scan_reason=login_backtrack_required`
  - `completion_block_reason=bbp_login_required`
  - `backtrack_original_observed_utc`
  - `backtrack_attempt_count`
- `out/systems/F/live/f_login_backtrack_evidence_live.csv`
  - append-only evidence of blocked, retried, and merged login rows
- `out/systems/F/price_list_manager/live/f061_browser_visibility_state.txt`
  - current auth/browser state
- `out/systems/F/price_list_manager/live/live_cycle_events.csv`
  - runtime events for UI and proof

New small control artifact:
- `out/systems/F/price_list_manager/live/f061_login_mode.requested`

Suggested fields:
- `requested_utc`
- `requested_by=operator_ui`
- `mode=login_recovery`
- `supplier_id`
- `run_id`
- `status=requested`
- `hold_seconds=60`
- `reason=operator_login_button`

Optional status artifact:
- `out/systems/F/price_list_manager/live/f061_login_mode_status.csv`

Suggested columns:
- `observed_utc`
- `mode_state`
- `supplier_id`
- `run_id`
- `login_pending_rows`
- `current_asin`
- `browser_mode`
- `auth_state`
- `last_probe_result`
- `notes`

## UI Design
Location:
- Existing `Price List Queue` page in `scripts/flows/O/O400_operator_ui.py`.

Add helper readers:
- `_price_list_login_counts(root, active_f061_run_id)`
- `_price_list_auth_state(root)`
- `request_price_list_login_mode_from_ui(root, supplier_id, run_id)`

Active scanner card changes:
- Add `LOGIN` between `FAIL` and `RE SCAN`.
- `LOGIN` count comes from current active run rows where:
  - `scan_status in {login_backtrack_pending, login_backtrack_running}`, or
  - `completion_block_reason=bbp_login_required`
- Add a Login button beside the active scanner status.

Button states:
- Red/enabled:
  - login pending rows > 0, or
  - `f061_browser_visibility_state.txt` has `auth_state=LOGIN_REQUIRED`
- Grey/disabled:
  - login pending rows = 0 and `auth_state=LOGGED_IN`
- Amber/enabled:
  - login mode already requested but no child has consumed it yet
- Blue/disabled:
  - login mode is active and the child is currently holding the browser open

Button action:
- Write `f061_login_mode.requested`.
- Append `login_mode_requested` to `live_cycle_events.csv`.
- Do not launch Chrome directly from the UI.
- Do not pause FPM with global maintenance.

## Runtime Design
Owner:
- `FPM130_run_live_cycle.py` remains the owner.

Normal overnight behavior:
- F061 continues to process normal pending rows.
- If a row needs BBP auth, F061 marks it `login_backtrack_pending` and moves on.
- The active run is not considered review-ready until login rows are cleared.

Automatic auth-attention behavior:
- When F061 reports real browser/auth blockage through `scanner_speed_browser_blocked_rows > 0`, FPM130 must treat that as operator attention needed.
- The next normal F061 child must use `F061_BACKGROUND_BROWSER_MODE=visible` from the normal scanner-owned child path.
- The browser must still be the normal F061 Chrome profile; do not open `FPM160_f061_visible_login_maintenance.py` or any standalone Chrome helper.
- An explicit emergency opt-out remains available with `FPM_F061_AUTO_VISIBLE_AUTH_ATTENTION=0`, but the default is visible because hidden repeat scanning leaves BBP/Amazon login-required rows parked indefinitely.
- Login-backtrack queue replay still uses the `f061_login_mode.requested` path when the operator wants the backlog processed first after authentication.

When Login Mode is requested:
1. FPM130 sees `f061_login_mode.requested` at a normal child boundary.
2. FPM130 starts the next F061 child with:
   - `F061_BACKGROUND_BROWSER_MODE=minimized`
   - `F061_LOGIN_MODE=1`
   - `F061_LOGIN_HOLD_SECONDS=900` for UI/operator requests
   - `F061_LOGIN_MODE_REQUEST_PATH=<request file>`
3. F061 selects the first `login_backtrack_pending` row with `completion_block_reason=bbp_login_required`.
4. F061 opens the normal script-owned browser on that row's ASIN URL.
5. F061 keeps the browser on the normal hidden path if only the BBP iframe/container is missing.
6. F061 surfaces the already-created BBP driver only after real login-option evidence:
   - Amazon `/ap/signin`, MFA, CVF, OTP, CAPTCHA, or sign-in controls
   - BBP login email/password/button controls
7. F061 waits for the operator to complete login without repeated external show loops.
8. F061 refreshes or reopens the same ASIN page and checks for login evidence:
   - success evidence: BBP cost field or usable BBP dashboard fields
   - failure evidence: login form still present or dashboard value `LOGIN`
9. If login succeeds:
   - write `login_mode_authenticated` event
   - clear or mark the request consumed
   - process login-backtrack rows first
   - merge recovered BBP evidence back into original rows
   - resume normal pending rows after login rows reach 0
10. If login still fails after the hold:
   - keep rows as `login_backtrack_pending`
   - write `login_mode_still_required`
   - leave the UI button red
   - do not burn the rows as normal failures

## Queue Ordering
Default normal mode:
- Prioritize ordinary `pending` rows when auth is missing, so overnight work continues.
- Do not repeatedly cycle login rows when no operator has requested Login Mode.

Login Mode:
- Prioritize rows in this order:
  1. `login_backtrack_pending` with `completion_block_reason=bbp_login_required`
  2. `login_backtrack_pending` with `dashboard_yes_no_backtrack_required`
  3. normal `pending`

After Login Mode success:
- Keep processing backtrack rows until login backlog is 0 or chunk ends.
- If chunk ends and login backlog remains, the next child should stay visible only while login mode is still active or auth state is not yet confirmed.

## Events And Health
New events in `live_cycle_events.csv`:
- `login_mode_requested`
- `login_mode_child_started`
- `login_mode_hold_started`
- `login_mode_authenticated`
- `login_mode_still_required`
- `login_mode_backlog_drained`
- `login_mode_resumed_normal`

New health/checklist rows:
- `f061_login_mode_request_state`
  - ok when no request or active request is being handled
  - warn when request is older than one child boundary
  - fail when request is active but no child can start
- `f061_login_backtrack_backlog`
  - ok when 0
  - warn when > 0
  - fail only if backlog grows while login mode has authenticated successfully

## Proof Plan
Isolated tests:
- UI helper counts login rows from active run.
- UI Login button writes only `f061_login_mode.requested` and event row.
- FPM130 starts the next child visible with login-mode env when request exists.
- F061 in normal mode skips login-backtrack rows if auth is missing and no login mode request exists.
- F061 in login mode picks the first login-required ASIN.
- F061 returns `BBP_LOGIN_REQUIRED` without completing rows when the 60 second hold expires.
- F061 processes and merges login-backtrack rows after authenticated evidence appears.

Live proof:
- Start with at least one `login_backtrack_pending` row.
- Press Login in UI.
- Confirm normal F061 child starts visible.
- Confirm the browser opens the first login-required ASIN from the active run.
- Confirm the child logs the 60 second login hold.
- After login, confirm:
  - `login_mode_authenticated` event exists
  - `login_backtrack_pending` count decreases
  - Stax pending rows decrease
  - no Google Sheets writes were made

## Implementation Phases
Phase 1 - UI visibility and control:
- Add LOGIN count to active scanner card and supplier row overlay.
- Add Login button states.
- Add request writer and tests.

Phase 2 - FPM130 request consumption:
- FPM130 detects request at child boundary.
- Starts next F061 child visible with login-mode env.
- Writes login-mode events.

Phase 3 - F061 login mode:
- Add login-mode selection and first-ASIN opening.
- Add 60 second login hold and refresh/recheck.
- Keep rows pending on failure.
- Replay login backlog first after authentication.

Phase 4 - Proof and guardrails:
- Add health rows.
- Add focused tests.
- Run one controlled live proof with an existing login backlog.

## Definition Of Done
- LOGIN count is visible in the Price List Queue UI.
- Login button is red only when action is needed and grey when logged in.
- Pressing Login never opens a separate standalone Chrome window.
- The next normal F061 child opens visible on the first login-required ASIN.
- The child waits 60 seconds, refreshes/rechecks, and records auth evidence.
- Login-backtrack rows are merged/backdated after login.
- Normal scanning resumes after login backlog drains.
- Review handoff remains blocked until login rows are 0.
