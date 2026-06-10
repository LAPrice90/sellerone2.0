# F Controlled Live Login Proof Window

Created: 2026-06-09
Owner: Rep and Operations
Approval source: Luke approved proceeding in Rep Chat after `F-SINGLE-LOGIN-SYSTEM-REBUILD` passed pre-live review.
Job reference: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`

## Plain-English Purpose

Luke has approved moving from pre-live F login readiness into a controlled live proof window.

This is not permission for uncontrolled login retries. It is permission for one bounded scanner-owned proof attempt under the rebuilt single-login system.

## What Is Approved

Approved:

- use the single F login controller
- use the scanner-owned browser/session path only
- enter bounded `login_attempt_mode`
- if the controller is still parked in `normal_scan_only`, perform the one bounded controller action needed to move into `login_attempt_mode` for this proof window
- attempt to prove Dashboard Yes/No
- record redacted proof
- if already logged in, confirm Dashboard Yes/No and continue safely
- if not logged in, proceed only through the approved controller route

## What Is Not Approved

Not approved:

- Amazon security bypass
- disabling MFA
- repeated SMS requests
- repeated phone/voice requests
- separate Chrome workaround
- direct cookie/profile manipulation
- OTP, cookie, token, credential, or raw secret storage
- UI login acting as its own login engine
- old scanner login racing the controller
- auto-login racing the controller
- price changes
- Google Sheets writes
- Product DB or local DB alignment
- purchase, receiving, or send-to-Amazon
- output deletion
- widening into A, B, E, H, or O

## Stop Conditions

Stop immediately and report to Rep if any of these appear:

- SMS unavailable
- phone/voice unavailable
- Amazon says wait, try later, too many attempts, tomorrow, or 24 hours
- captcha
- passkey
- authenticator-only
- account recovery
- manual challenge
- no fresh code available
- browser/profile/cookie change would be needed
- more than one code/SMS/phone attempt would be needed
- the login controller is not the sole owner
- Chrome opens outside the scanner-owned path
- more than one controller-mode promotion would be needed

## Approval Clarification - 2026-06-09

Luke's approval to proceed covers the next bounded controller action from `normal_scan_only` into real Seller Central `login_attempt_mode` for this proof window.

This is not approval for repeated retries. It is one controlled mode promotion so the already-approved scanner-owned proof attempt can actually run.

If the proof attempt then hits any stop condition above, Operations must stop and report the blocker instead of asking for another retry.

## Maintenance Approval Clarification - 2026-06-09

Luke approved the controlled F owner reload/relaunch needed when the existing scanner child is already running behind the old `normal_scan_only` gate.

The detailed approval record is `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md`.

Operations does not need to ask Luke again for this named reload/relaunch action. It must still stay inside the F-only target, single controller route, no-repeat login attempt, and stop conditions in this proof window.

## Success Result

Success means:

- Dashboard Yes/No is proved through the scanner-owned path
- no repeated SMS/phone attempt occurred
- no Amazon security bypass occurred
- proof is redacted
- held login-required F work can safely resume through the normal F path

## Safe Failure Result

Safe failure means:

- F stops without hammering Amazon
- exact redacted blocker is recorded
- cooldown/manual-challenge state is recorded
- earliest safe retry or Luke decision is recorded
- logged-out price-file continuation remains available

## Operations Instruction

Route this to the existing F Worker/Operations path.

Do not create a new manager.

Rep Chat only needs the business result:

- logged in and proved
- safely blocked with exact reason
- Luke decision needed
