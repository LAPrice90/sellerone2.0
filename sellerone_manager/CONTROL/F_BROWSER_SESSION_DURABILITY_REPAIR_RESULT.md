# F Browser Session Durability Repair Result

Generated UTC: 2026-06-09T12:55:00Z
Job ref: `F-BROWSER-SESSION-DURABILITY`
Worker role: SellerOne F Worker

## Result

Code fix applied and isolated durability verification passed.

The packet is not safe to mark `fixed_needs_retest` yet because the broader packet retest still has unrelated `tests/test_fpm130_live_cycle.py` failures outside this browser/profile ownership scope. Treat this like fixing the lock and key report, but finding that a different checklist for rescan routing still fails.

## What Changed

- `scripts/flows/F/login_controller.py`
  - Fixed the browser-session durability default path helper so the report/state paths resolve correctly.
  - Added read-only profile classification: `approved`, `mismatch`, `temporary`, or `unknown`.
  - Added read-only cookie/session classification: `present`, `missing`, `expired`, `reset-risk`, or `unknown`.
  - Added redacted approved profile proof, stable-path proof, and startup/recovery/cleanup reset-risk summary to the durability report and state JSON.
  - Added a refresh helper that rebuilds state/report from existing redacted events without appending fake live events.
  - Kept `still_required` login requests active so scanner-owned login mode is not dropped while a login is still required.

- `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - The child scanner environment now explicitly carries the approved scanner-owned BBP profile defaults:
    - user-data source: redacted local `Chrome_UC136`
    - profile: `Profile 2`

- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
  - Aligned the standalone profile-window surfacing default to `Profile 2` when env values are absent.

- `tests/test_f_login_controller.py`
  - Added focused proof that the report names the approved scanner-owned profile without raw paths.
  - Added focused proof that a temporary profile is classified as reset risk and redacted.
  - Added focused proof that the report includes profile proof even when no recent events exist.

- `tests/test_fpm130_live_cycle.py`
  - Added focused proof that FPM declares the approved BBP profile in the F061 child env.

## Proof Files Refreshed

- `out/systems/F/price_list_manager/live/f_browser_session_durability_report_latest.md`
- `out/systems/F/price_list_manager/live/f_browser_session_durability_state.json`

The report now says:

- profile source: scanner-owned F061/BBP Chrome profile
- profile state: approved
- profile path stable: yes
- cookie/session state: unknown
- cleanup path: singleton lock cleanup only; no browser cookie, cache, or profile folder deletion
- reset risk: low

## Rollback Snapshot

Before refreshing the proof files, the previous durability proof files were copied to:

`out/systems/F/price_list_manager/live/f_browser_session_durability_backup_20260609T124707Z`

No output was deleted.

## Verification

Passed:

- `python -m pytest tests/test_f_login_controller.py -q`
  - 9 passed
- `python -m pytest tests/test_fpm130_live_cycle.py::test_fpm130_default_bbp_profile_is_plugin_profile tests/test_fpm130_live_cycle.py::test_fpm130_child_env_declares_approved_bbp_profile tests/test_fpm130_live_cycle.py::test_fpm130_login_mode_visible_child_surfaces_configured_profile tests/test_fpm130_live_cycle.py::test_fpm130_login_mode_show_filter_targets_configured_profile -q`
  - 4 passed
- `python -m pytest tests/test_f_legacy_webscrape_money_input.py -q`
  - 54 passed
- Redaction scan across the refreshed durability report, state, and events found no raw `C:\Users\Luke` path, obvious cookie/token/password/credential assignment, OTP value, six-digit code, or `secret` hit.

Read-only MOT:

- `python -m sellerone_manager.app --hourly-mot --mot-flow F`
  - status: `decision_needed`
  - fail count: 1
  - warn count: 2
  - remaining fail: `f_rescan_priority_proof`, which needs a protected decision and is outside this browser-session durability repair.

Did not pass:

- Full `python -m pytest tests/test_fpm130_live_cycle.py -q`
  - 84 passed
  - 3 failed
  - failing tests:
    - `test_fpm130_promotes_ai_rescan_before_current_supplier_pending`
    - `test_fpm130_promotes_operator_rescan_event_before_normal_pending_rows`
    - `test_fpm130_force_rebuilds_review_pack_when_ai_rescan_completes`
  - These failures are about rescan/review-pack routing, not browser profile/session durability. Repairing them would widen beyond the approved browser/profile ownership scope.

## Protected Actions

Not performed:

- no live F061 run
- no FPM/F061 restart
- no Amazon login or security action
- no MFA bypass or disablement
- no OTP, cookie, token, credential, or raw secret exposure
- no separate Chrome workaround
- no browser profile/cookie mutation
- no queue edit outside status commands
- no output deletion
- no prices, Sheets, databases, purchase, receiving, or send-to-Amazon action

## Blockers

1. Generic claim command issue:
   - affected job: `A-BLOCKED-EVIDENCE-USERS`
   - attempted action: required `python -m sellerone_manager.app --claim-approved-task`
   - failure: the generic queue claim selected `A-BLOCKED-EVIDENCE-USERS` instead of the delegated `F-BROWSER-SESSION-DURABILITY` packet.
   - safest proposed fix: Rep or Operations should reconcile that accidental claim. This worker did not move the A packet back because it is outside this packet boundary.

2. Broad FPM retest failures:
   - affected job: `F-BROWSER-SESSION-DURABILITY`
   - attempted action: packet retest file `tests/test_fpm130_live_cycle.py`
   - failure: 3 unrelated rescan/review-pack tests fail.
   - safest proposed fix: open or route a separate FPM rescan/review-pack repair packet, or explicitly approve accepting this browser-session durability repair with those unrelated failures still present.

## Status Recommendation

Do not mark `fixed_needs_retest` yet.

Recommended queue state: blocked until the scope decision above is resolved.
