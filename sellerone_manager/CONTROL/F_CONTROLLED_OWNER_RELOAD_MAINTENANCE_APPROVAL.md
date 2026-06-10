# F Controlled Owner Reload Maintenance Approval

Created: 2026-06-09
Owner: Rep and Operations
Approval source: Luke approved in Rep Chat after the controlled live proof found the active scanner child was already running behind `normal_scan_only`.
Applies to: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`

## Plain-English Decision

Luke has approved the controlled F owner reload/relaunch needed to complete the already-approved Seller Central live proof window.

This is allowed because SellerOne maintenance mode exists for approved repairs and additions. Operations does not need to stop and ask Luke again for this same F reload/relaunch action.

## Why This Is Needed

The single-login rebuild passed pre-live review.

The controlled live proof then found:

- the scanner child was already running
- it was running behind the old `normal_scan_only` gate
- the new `login_attempt_mode` promotion must be set before the scanner child starts
- creating a second child would create a second owner, which is forbidden

Plain English: the old child is already driving with the old road signs. We need a controlled owner reload so the next child starts with the new road signs.

## Approved Target

Approved target:

- F price list scanner owner only
- existing scanner-owned F path only
- single login controller only
- bounded Seller Central live proof route only

## Approved Action

Operations may approve Worker action to:

- stop or allow exit of the existing F scanner child if needed
- relaunch/reload the F scanner owner through the existing approved F path
- set the one bounded controller promotion into `login_attempt_mode`
- attempt the same single scanner-owned Dashboard Yes/No proof
- record redacted proof
- run read-only F MOT after the attempt

## Preferred Method

Use the softest safe method available:

1. Prefer natural child exit if it is already ending promptly.
2. If it is still blocking the approved proof, use the named F owner reload/relaunch route.
3. Do not create a second scanner owner.
4. Do not use a blind kill unless the maintenance record says why a softer method cannot work.

## Still Not Approved

This approval does not allow:

- repeated SMS or phone attempts
- Amazon security bypass
- MFA disablement
- separate Chrome workaround
- browser/profile/cookie manipulation
- OTP, cookie, token, credential, or raw secret storage
- price changes
- Google Sheets writes
- Product DB or local DB alignment
- purchase, receiving, or send-to-Amazon
- output deletion
- widening into A, B, E, H, or O
- permanent Task Scheduler change

## Stop Conditions

Stop and report to Rep if:

- SMS unavailable
- phone/voice unavailable
- Amazon says wait, try later, too many attempts, tomorrow, or 24 hours
- captcha
- passkey
- authenticator-only
- account recovery
- manual challenge
- no fresh code available
- more than one SMS/phone/code attempt would be needed
- more than one controller-mode promotion would be needed
- Chrome opens outside the scanner-owned path
- the login controller is not the sole owner
- reload/relaunch would require a blind kill without clear proof

## Required Proof

Operations or Worker must record:

- what F owner/child was active before reload
- how it was stopped or allowed to exit
- how the new owner was launched
- whether the controller promotion was consumed
- Dashboard Yes/No result
- whether any Amazon stop condition appeared
- read-only F MOT result

## Business Result Needed By Rep

Rep Chat only needs one of:

- logged in and Dashboard Yes/No proved
- safely blocked with exact redacted reason
- Luke decision needed for a new Amazon/security condition
