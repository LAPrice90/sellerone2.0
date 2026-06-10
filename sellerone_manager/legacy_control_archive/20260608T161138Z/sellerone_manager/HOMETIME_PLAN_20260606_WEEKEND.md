# Weekend Hometime Plan - 2026-06-06 to 2026-06-08

## Plain-English Goal
Make F boring by Monday morning.

That means: when Seller Central asks F to log in, F uses the normal scanner-owned browser, classifies the page it sees, uses the approved code source if a code is available, proves Dashboard Yes/No, and then keeps scanning or parks with one exact blocker.

## Current Truth Before Weekend Mode
- `F-LOGIN-CONTROLLER-REWRITE` is the active F job.
- F focused tests passed for the login controller and scanner money-input fallback.
- The live scanner-owned browser reached Seller Central Two-Step Verification.
- The latest page pull says `Two-Step Verification Enter the code`.
- The current blocker is `no_fresh_code` in the approved code source.
- Dashboard Yes/No is not yet proved for the current Seller Central challenge.

## Weekend Priority Order
1. F login/code-source proof and Dashboard Yes/No proof.
2. F scanner forward-progress proof once login is stable.
3. B order/token proof checks for Monday restocking readiness.
4. O restock view readiness checks.
5. E/H read-only confidence and safety checks only.

## F Preflight Before Hometime
F must confirm:
- the scanner-owned browser reaches Seller Central when login is required.
- the page pull records the exact challenge.
- the approved email-code source either sees a fresh code or proves why it does not.
- any Amazon alternate verification path is recorded as a clear state, not hidden behind a generic login failure.

## F Monitoring Cadence
- Active automation: `sellerone-manager-coordinator-pulse`.
- F child-style check: every 10 minutes while Seller Central login is unresolved.
- Main Hometime refresh: every 30 minutes, run by the same heartbeat when the latest Hometime pulse is old enough.
- Once F proves Dashboard Yes/No and scanner progress continues, F drops to 30-minute checks.
- If F repeats the same blocker twice with no new evidence, it must change tactic inside the approved packet or park with the exact blocker.

Only one thread heartbeat is allowed in the Codex app, so the weekend setup uses one combined heartbeat instead of creating a duplicate child heartbeat. Do not recreate `sellerone-hometime-mode-pulse` unless the active manager heartbeat is first retired or moved.

## F Success Definition
Credentials submitted is not success.

F is successful only when:
- the code/passkey/challenge page is classified clearly, and
- Dashboard Yes/No becomes `YES`, `NO`, or `LIKELY`, and
- the scanner continues or every remaining affected row has a clear blocker reason.

## Luke Interruption Rule
Ask Luke only if Amazon needs a real human code, passkey, captcha, or manual challenge and F cannot safely continue.

Do not send repeat emails for the same blocker. Do not email for routine B/O warnings.

## Hard Boundaries
Do not:
- change prices.
- edit queues.
- write Google Sheets.
- align Product DB or local DB facts.
- delete or rewrite scanner outputs.
- create purchase orders.
- receive stock.
- send stock to Amazon.
- restart workers without a separate approved proof window.
- open a separate Chrome login workaround.
- mark login proved without Dashboard Yes/No proof.

## Monday Morning Output
The Monday morning summary must classify F as one of:
- `proved`: Dashboard Yes/No proved and scanner continued.
- `parked with exact blocker`: no fresh code, passkey/security-key, captcha, missing email source, or manual challenge.
- `needs Luke`: only for a real human challenge that F cannot complete safely.
