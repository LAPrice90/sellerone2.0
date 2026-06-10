# F Seller Central Safe Login Today Plan

Created: 2026-06-09
Owner: Rep and Operations
Priority: urgent business blocker
Mode: management plan, worker execution required

## Plain-English Purpose

F cycle is a business-growth blocker.

The acceptable outcome is not "more investigation" by itself. The acceptable outcome is that F can handle Seller Central login safely without repeatedly triggering Amazon phone/SMS blocking, and without relying on Luke to babysit the scanner.

## Current Plan Clarity

The plan is about 70 percent clear.

Clear parts:

- F must not repeatedly request phone/SMS verification.
- F must not bypass Amazon security.
- F must use one scanner-owned browser/session path, not a separate Chrome workaround.
- Login success must be proved by Dashboard Yes/No, not by "credentials were submitted."
- F must use cooldown/manual-challenge states when Amazon blocks SMS, shows MFA risk, or requires a human decision.
- Existing tickets already cover login controller rewrite, cooldown switch, MFA cooldown policy, and browser session durability.

Unclear or unfinished parts:

- The work is split across too many F tickets, so the finish line is not visible enough.
- Browser-session durability is still waiting proof.
- The exact safe re-enable path from `normal_scan_only` to bounded `login_attempt_mode` needs one clear owner and proof route.
- The queue needs a single "today" priority lane for the F login outcome.
- If Amazon presents a real manual challenge, the worker must stop and escalate instead of experimenting.

## Today Outcome Required

By end of today, Operations should aim for one of these outcomes:

### Best Outcome

F logs in through the approved scanner-owned path, avoids repeated phone/SMS triggering, proves Dashboard Yes/No, and records redacted proof.

### Acceptable Safe Outcome

F cannot complete login because Amazon requires a human/security decision, but it stops safely, records the exact redacted blocker, cooldown state, earliest safe retry time, and what Luke must decide.

### Unacceptable Outcome

- repeated phone/SMS attempts
- vague "login failed" status
- separate Chrome workaround
- hidden credential/cookie/session manipulation
- scanner restart without proof window
- no clear blocker after another attempt

## Execution Order

1. Consolidate the F login state.
   - Read current F login controller, cooldown, and browser-session proof.
   - Confirm current mode: `normal_scan_only`, `login_attempt_mode`, `soft_cooldown`, `hard_cooldown`, or `manual_challenge`.

2. Close browser-session durability proof.
   - Confirm whether F is using the approved scanner-owned profile.
   - Confirm whether cookies/session are preserved.
   - Label login reason: profile mismatch, temporary profile, cookie missing, cookie expired, Amazon forced MFA, manual challenge, or unknown.

3. Prepare one bounded login attempt path.
   - Only if not in cooldown/manual challenge.
   - Only through the scanner-owned browser.
   - Only with redacted proof.
   - No repeated phone/SMS attempts.

4. Run the bounded proof route if safe.
   - Prove Dashboard Yes/No.
   - If Amazon blocks phone/SMS or shows manual challenge, stop and record the state.

5. Report business result to Rep.
   - logged in and safe
   - blocked by Amazon/manual challenge
   - code/session issue found and repaired
   - needs Luke decision

## Worker Boundaries

Allowed:

- F login/controller/session code work inside approved F packets
- focused local tests
- read-only F MOT
- redacted proof notes
- one bounded login attempt only if the approved F proof path says it is safe

Forbidden:

- Amazon security bypass
- disabling MFA
- repeated SMS/phone requests
- separate Chrome workaround
- storing OTPs, cookies, tokens, credentials, or raw secrets
- queue edits
- output deletion
- price changes
- Google Sheets writes
- Product DB or local DB alignment
- purchase, receiving, or send-to-Amazon
- widening into A, B, E, H, or O

## Luke Escalation

Escalate only if Amazon requires a human/security decision or a protected action is needed.

Escalation should include:

- what F saw
- current safe state
- whether Amazon blocked SMS/phone
- earliest safe retry time
- what decision Luke needs to make

No secrets, OTPs, cookies, tokens, credentials, or full phone numbers.

## Recommended Queue Action

Create or elevate a single umbrella job:

- `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`

This does not replace the existing F tickets. It coordinates them around the business outcome for today.

## Success Measure

F is no longer "stuck" as a vague login problem.

It is either:

- safely logged in and continuing through the scanner-owned path, or
- safely parked with a precise Amazon/security blocker and no repeated phone/SMS damage.
