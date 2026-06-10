# F Browser Session Durability Review

Reviewed UTC: 2026-06-09T12:35:00Z
Reviewer role: SellerOne Reviewer
Packet: `tasks/approved/MGR_F_BROWSER_SESSION_DURABILITY_V1.md`
Job ref: `F-BROWSER-SESSION-DURABILITY`

## Decision

FAIL.

The browser-session durability proof does not satisfy the packet acceptance proof yet.

Plain English: the proof is like a house-key checklist that says "we saw a locked door", but it still does not prove which keyring F is using, whether it is the same keyring every time, or whether any cleanup step is throwing the keys away.

## Evidence Reviewed

- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\f_browser_session_durability_report_latest.md`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\f_browser_session_durability_state.json`
- `C:\Users\Luke\Desktop\SellerOne 2.0\out\systems\F\price_list_manager\live\f_browser_session_events.csv`
- `C:\Users\Luke\Desktop\SellerOne 2.0\scripts\flows\F\login_controller.py`
- `C:\Users\Luke\Desktop\SellerOne 2.0\tests\test_f_login_controller.py`
- focused text search across relevant F scripts and F tests

No live scanner restart, live F061 run, Amazon bypass, separate Chrome workaround, cookie/profile mutation, queue edit, output deletion, price change, Sheet write, DB alignment, purchase, receiving, or send-to-Amazon action was performed by this review.

## Acceptance Check Results

| Acceptance check | Result | Review note |
|---|---|---|
| Redacted browser-session durability report exists | PASS | The report exists at the repo-root `out` path. |
| Report explains which profile F uses | FAIL | The latest report does not name the approved scanner-owned profile or explain the profile source. |
| Report explains whether the profile path is stable | FAIL | The report has no stable profile-path proof. |
| Report checks whether startup, recovery, or cleanup can reset cookies/cache | FAIL | The report does not inspect or summarize startup, recovery, or cleanup reset risk. |
| Tests prove approved scanner-owned profile path | FAIL | Relevant tests mention scanner-owned visible handling, but review did not find a focused test proving the approved profile path itself. |
| Tests prove no temporary fallback when auto-login is available | FAIL | Review did not find a focused test proving temporary profile fallback is blocked when auto-login is available. |
| Logs redact credentials, cookies, tokens, and OTPs | PARTIAL PASS | `test_browser_session_durability_logs_reason_labels_and_redacts_secrets` checks redaction of email, OTP, password, and a local path in report output. This is useful, but it does not by itself prove cookie/token redaction across all durability outputs. |
| Future login events have clear reason labels | PARTIAL PASS | Code supports labels including `profile_mismatch`, `temporary_profile`, `cookie_missing`, `cookie_expired`, `amazon_forced_mfa`, `manual_challenge`, and `unknown`. Current live evidence still records `unknown` for the latest reason. |
| No protected actions occurred | PASS | This review only read files and wrote this review artifact. |

## Blocking Evidence

The latest durability report says:

- page type is `seller_central_signin`
- status is `disabled`
- reason is `normal_scan_only`
- reason code is `unknown`
- result is `blocked`
- blocker is `normal_scan_only`

The latest durability state says:

- `profile_state` is `unknown`
- `cookie_state` is `unknown`
- `latest_reason_code` is `unknown`
- the last 50 recorded reason codes are all `unknown`

That means the proof still cannot answer the central question from the packet: whether F is using the approved durable browser profile or losing session state because of profile/cookie handling.

## Safest Proposed Fix

Return this packet to Builder repair with a narrow proof-only scope:

- make the durability report explicitly name the approved scanner-owned profile source and whether the profile path is stable
- add read-only checks that classify profile state as approved, mismatch, temporary, or unknown without exposing the raw profile path if it is sensitive
- add read-only checks that classify cookie/session state as present, missing, expired, reset-risk, or unknown without printing cookies
- inspect F startup, recovery, and cleanup code paths and summarize whether any path can remove or replace the browser profile, cookies, or cache
- add focused tests proving approved scanner-owned profile use and no temporary profile fallback when auto-login is available
- keep all secret material redacted in report, state, events, and logs

Do not force a live scanner restart. Live durability proof should still wait for natural scanner-owned login/session events after focused tests pass.

## Review Outcome

Status recommendation: `retest_failed`.

I did not move the packet status because this delegated review explicitly forbade queue edits unless closing a sufficient proof. The proof is not sufficient.
