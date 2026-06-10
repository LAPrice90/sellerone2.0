# F Single Login System Risk Reduction Gates

Created: 2026-06-09
Owner: Rep and Operations
Applies to: `F-SINGLE-LOGIN-SYSTEM-REBUILD`
Status: mandatory before live login proof

## Plain-English Purpose

The F rebuild should not jump straight from a messy three-login system into another live login attempt.

These gates raise the chance of success by forcing the worker to prove the system is calm before touching Seller Central again.

## Gate 1 - Containment Audit

Before any rebuild or live proof, the worker must identify every login entry point:

- UI login button
- old scanner Chrome/open-browser login
- auto-login path
- F061/FPM login calls
- browser profile creation and reuse
- any fallback or recovery path that opens Chrome

Pass condition:

- A redacted map exists showing every login entry point and which controller owns it.

Stop condition:

- If any live process is actively opening Chrome or attempting login outside the controller, stop and report a containment blocker.

## Gate 2 - Login Attempt Freeze

Until one controller owns the routes, F should not attempt Seller Central login.

Allowed:

- local code inspection
- local tests
- read-only F MOT
- controller-level guard that blocks login attempts
- logged-out scanning design and tests

Not allowed:

- live Seller Central login
- SMS/code request
- voice-call request
- browser/profile/cookie mutation
- separate Chrome workaround
- restarting F to force login

If the only way to stop active login attempts is to pause F runtime, Operations must request a named F-only maintenance action with:

- target
- reason
- exact pause method
- exact restart method
- health proof after restart

## Gate 3 - Single State Dashboard

The worker must create or update one redacted state view for F login.

It should show:

- Dashboard Yes/No
- current login mode
- active browser profile owner
- whether login attempts are frozen
- cooldown/manual-challenge state
- held price files
- rows waiting for Seller Central second check
- next safe action

Pass condition:

- Operations and Rep can tell the F state without watching Chrome flash on screen.

## Gate 4 - Logged-Out Continuation Test

Before any live login proof, prove F can keep moving without login.

The worker must test:

- a price file can continue in logged-out mode
- login-required rows are marked for second check
- the file is held for login instead of sent to user review
- F moves to the next price file
- when login returns, held files are selected for completion

Pass condition:

- Focused tests prove no price file stalls just because Seller Central is unavailable.

## Gate 5 - Human-Assist Path

The UI login button must become a controlled help request.

It should:

- call the single login controller
- show the current state
- show what Amazon is asking for
- warn against repeated SMS/code clicks
- wait without racing old login routes

It should not:

- own login itself
- open a separate browser path
- reset cookies or profiles
- compete with auto-login

Pass condition:

- Focused tests or review evidence prove the UI button routes through the controller.

## Gate 6 - Live Proof Readiness

A live login proof can be considered only after:

- all login entry points are mapped
- duplicate login owners are routed or retired
- login attempts are frozen until controller-owned
- state dashboard exists
- logged-out continuation is tested
- UI button routes through controller
- no Amazon cooldown/manual challenge is active
- Operations confirms the approved proof boundary

If any Amazon security challenge appears, the worker must stop and report the redacted state.

## Business Success Definition

The win is not just "login worked once."

The win is:

- F has one login owner
- Chrome stops appearing unpredictably
- UI login no longer competes with auto-login
- logged-out mode keeps price files moving
- TD Synnex-style files are held and resumed
- user review is reserved for real business uncertainty
- live Amazon interaction is calm, controlled, and redacted

## Protected Boundary

This gate document does not approve:

- live Seller Central login
- SMS/code request
- voice-call request
- Amazon security bypass
- MFA disablement
- browser/profile/cookie mutation
- F runtime pause/restart
- Task Scheduler change
- price, Sheet, database, purchase, receiving, or send-to-Amazon action
- output deletion

Any F runtime pause/restart must use the approved maintenance process first.
