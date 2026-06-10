# F Repair Package - Browser Session Durability V1 - 2026-06-06

## Manager Authority
- task_id: MGR_F_BROWSER_SESSION_DURABILITY_V1
- job_ref: F-BROWSER-SESSION-DURABILITY
- status: blocked_needs_luke
- authority: luke_approved_safe_investigation_and_code_repair
- luke_action_required: 1

## Plain-English Idea
F can now log in, but it may still be losing the login because our own browser handling is not durable enough.

Think of the browser profile like a set of house keys. If F opens the right house but throws away the keys after each visit, Amazon will keep asking it to prove who it is. This task checks whether F is using the same approved scanner-owned Chrome profile, whether any cleanup step is wiping cookies/cache, and whether future login requests are Amazon-enforced or self-inflicted.

## Working Theories To Test
- F sometimes starts with the wrong Chrome profile instead of the approved BBP plugin profile.
- F starts a temporary browser profile, so cookies disappear when the child browser closes.
- A cleanup or recovery path removes browser session files after a crash or relaunch.
- Multiple browser owners compete, causing Amazon to see fresh or suspicious sessions.
- The scanner does not record whether the login was caused by BBP, Seller Central, expired cookie, missing cookie, passkey/OTP, or profile mismatch.
- Amazon may still expire sessions normally, but F should label that clearly instead of treating every login as the same failure.

## Boundary
- allowed_scope: - `scripts/flows/F/login_controller.py` - `scripts/flows/F/bbp_login_recovery.py` - `scripts/flows/F/seller_central_login_recovery.py` - `scripts/flows/F/_scanner_state.py` - `scripts/flows/F/F061_run_legacy_first_checks_local.py` - `scripts/flows/F/legacy_scanner_2_1/Webscrape.py` - narrow browser/profile ownership checks in `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py` - focused F tests under `tests/` - redacted session-durability proof files under `out/systems/F/price_list_manager/live/` - read-only manager/MOT proof wording if needed
- forbidden_actions: - Do not bypass Amazon security. - Do not disable MFA, suppress OTP, or store one-time codes. - Do not print or log credentials, cookies, tokens, OTPs, or raw browser secrets. - Do not open a separate Chrome login workaround. - Do not run F061 live during code repair. - Do not restart FPM or F061 without a separate approved proof window. - Do not edit F061 queue state. - Do not delete or rewrite scanner outputs. - Do not switch suppliers. - Do not change prices. - Do not write Google Sheets. - Do not align Product DB or local DB facts. - Do not delete outputs. - Do not widen into A, B, E, H, or O work.
- proof_required: - Produce a redacted browser-session durability report explaining which profile F uses, whether the profile path is stable, and whether any startup/recovery/cleanup path can reset cookies/cache. - Add or adjust tests proving F uses the approved scanner-owned profile path and does not fall back to a temporary profile when auto-login is available. - Add or adjust tests proving session-durability logs redact credentials, cookies, tokens, and OTPs. - Add a clear reason code for future login events: `profile_mismatch`, `temporary_profile`, `cookie_missing`, `cookie_expired`, `amazon_forced_mfa`, `manual_challenge`, or `unknown`. - Retest with focused F tests and read-only F MOT. - Live durability proof can happen only by observing natural scanner-owned login events after tests pass; do not force a live scanner restart for this task.
- retest_command: python -m pytest tests/test_f_login_controller.py tests/test_fpm130_live_cycle.py tests/test_f_legacy_webscrape_money_input.py -q; python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: - Use git diff for code rollback. - Do not edit F queue files, scanner outputs, credentials, cookies, or browser profile contents during rollback. - Remove or ignore only new redacted proof files created by tests. - Rerun read-only F MOT after rollback.
- stop_condition: Stop immediately if the work requires bypassing Amazon security, changing credentials, editing cookies directly, opening a separate browser workaround, queue edits, output deletion, scanner restart, supplier switch, Sheet write, price change, local DB alignment, or business judgement. Stop successfully when F has a redacted session-durability report, tests prove profile/session handling is stable, and future login events have clear reason labels instead of vague "login needed" status.

## Source
- source_type: luke_approved_chat_request
- source_id: F_BROWSER_SESSION_DURABILITY_20260606
- source_path: sellerone_manager/goals/active/GOAL_F_BROWSER_SESSION_DURABILITY_20260606.md

## Expected Output Files
- `out/systems/F/price_list_manager/live/f_browser_session_durability_state.json`
- `out/systems/F/price_list_manager/live/f_browser_session_durability_report_latest.md`
- `out/systems/F/price_list_manager/live/f_browser_session_events.csv`

## Exact Source Row
```json
{
  "source_id": "F_BROWSER_SESSION_DURABILITY_20260606",
  "source_path": "sellerone_manager/goals/active/GOAL_F_BROWSER_SESSION_DURABILITY_20260606.md"
}
```
