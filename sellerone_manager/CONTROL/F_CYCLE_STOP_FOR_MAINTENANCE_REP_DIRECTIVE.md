# F Cycle Stop For Maintenance - Rep Directive

Updated: 2026-06-09 14:39 UK
Owner: Rep / Operations
Job: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`

## Luke Decision

Luke has clarified that F is not to be treated as partly working.

Plain-English decision:

- F cycle is considered broken until the Seller Central login flow is repaired and proved.
- The visible business symptom is TD Synnex end-of-file stagnation. Luke reports F has been stuck there for days.
- Do not describe F as successfully logged in unless Seller Central proof has passed.
- Do not treat timestamp refresh, `Catching Up`, or broad `LOGGED_IN` wording as real progress.
- BBP login and Seller Central login must be reported separately.
- The active F cycle should be stopped or paused under approved F maintenance authority so repair can happen cleanly.

## Operations Instruction

Operations should:

1. Use the approved F maintenance authority to stop or pause the active F cycle safely.
2. Avoid creating a second F owner.
3. Keep F out of normal business scanning while the login repair is being applied.
4. Ensure only the single F login controller owns Seller Central login decisions.
5. Remove mixed status language such as broad `LOGGED_IN` where it can hide Seller Central not being proved.
6. Restart F only inside a bounded proof window once the repair is ready.

## Required Repair Outcome

The F repair is not complete until the system clearly separates:

- BBP logged in
- Seller Central logged in
- Seller Central login required
- Seller Central proof blocked
- scanner continuing in logged-out mode
- supplier/file parked for later Seller Central recheck

## Proof Required Before Normal Resume

Before F returns to normal runtime, proof must show:

- one controller-owned Seller Central login path
- no UI login path competing with old scanner or auto-login paths
- no false `LOGGED_IN` status for Seller Central
- Dashboard Yes/No proof is clear
- logged-out continuation parks blocked supplier work instead of stalling
- TD Synnex either moves past the current stuck end-of-file point or is cleanly parked for later Seller Central recheck while the next price file continues
- post-restart health evidence is recorded

## Boundaries

Still forbidden:

- Amazon security bypass
- repeated SMS, phone, or code attempts
- separate Chrome workaround
- browser profile or cookie mutation unless explicitly approved
- price changes
- Sheet writes
- Product DB or local DB alignment
- output deletion
- second F owner
