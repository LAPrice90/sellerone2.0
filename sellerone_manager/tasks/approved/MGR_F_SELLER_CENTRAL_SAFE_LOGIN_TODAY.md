# F Seller Central Safe Login Today

## Manager Authority
- task_id: MGR_F_SELLER_CENTRAL_SAFE_LOGIN_TODAY
- job_ref: F-SELLER-CENTRAL-SAFE-LOGIN-TODAY
- flow: F
- task_type: urgent_business_blocker_coordination
- status: in_progress
- authority: luke_requested_f_cycle_asap_2026-06-09
- priority: urgent
- luke_action_required: 0

## Plain English
F cycle is stuck on Seller Central login/session handling, and this is blocking business growth.

Luke has clarified that F must be treated as not working and not trusted live until Seller Central proof actually passes. Do not call F healthy, logged in, or catching up based on `LOGGED_IN`, `Catching Up`, heartbeat refresh, or timestamp refresh alone.

Active business symptom:

- F has been stuck at the end of the TD Synnex price file for days.
- Fresh status-file updates do not equal real progress.
- BBP authentication is not Seller Central Dashboard Yes/No proof.

This task coordinates the existing F login controller, cooldown, MFA policy, and browser-session durability work around one outcome today: safe scanner-owned login without repeatedly triggering Amazon phone/SMS blocking.

## Allowed Work
- read `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md`
- read `CONTROL/F_CONTROLLED_LIVE_LOGIN_PROOF_WINDOW.md`
- read `CONTROL/F_SINGLE_LOGIN_SYSTEM_FINAL_PLAN.md`
- read `CONTROL/F_SINGLE_LOGIN_SYSTEM_FINAL_FLOW.mmd`
- read `CONTROL/F_SELLER_CENTRAL_SAFE_LOGIN_TODAY_PLAN.md`
- read `CONTROL/F_SELLER_CENTRAL_BINARY_LOGIN_FLOW.md`
- use the approved F login/controller/session packets as the working boundary
- inspect current F login mode and redacted proof
- finish or retest browser-session durability
- run focused local tests
- run read-only F MOT
- use a bounded scanner-owned login proof route only if the existing F proof path says it is safe
- perform the one bounded controller-mode promotion from `normal_scan_only` into `login_attempt_mode` covered by `CONTROL/F_CONTROLLED_LIVE_LOGIN_PROOF_WINDOW.md`
- perform the controlled F owner reload/relaunch covered by `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md` if the active scanner child is already running behind the old gate
- record redacted outcome proof
- keep F stopped from normal business scanning while the repair is applied
- repair the single-login controller/status model before normal F runtime resumes
- separate BBP auth state from Seller Central auth state in user/operator-facing status
- remove or route competing UI login, old scanner login, and auto-login behavior through the single controller
- park or hold login-required supplier work when Seller Central is unavailable instead of stagnating or sending bad review work

## Forbidden Work
- no Amazon security bypass
- no MFA disablement
- no repeated SMS or phone requests
- no separate Chrome workaround
- no OTP, cookie, token, credential, or raw secret storage
- no queue edits outside approved packet status updates
- no output deletion
- no price changes
- no Google Sheets writes
- no Product DB or local DB alignment
- no purchase, receiving, or send-to-Amazon
- no widening into A, B, E, H, or O

## Acceptance Proof
- F maintenance-stop request is acknowledged, or a named blocker explains why the safe drain cannot be reached without a stronger protected action.
- TD Synnex moves past the stuck end-of-file point, or Seller Central remains unavailable and F cleanly parks/holds TD Synnex login-required work, moves to the next price file, and records a return path for later second-check.
- `LOGGED_IN` is not used for Seller Central unless Dashboard Yes/No proof has passed.
- BBP auth and Seller Central auth are reported separately.
- UI login, old scanner login, and auto-login do not compete; there is one controller owner.
- F is safely logged in through the scanner-owned path with Dashboard Yes/No proof, or
- F is safely parked with exact redacted blocker, cooldown/manual-challenge state, earliest safe retry time, and Luke decision if needed.
- The proof window boundaries in `CONTROL/F_CONTROLLED_LIVE_LOGIN_PROOF_WINDOW.md` are followed.
- The F owner reload/relaunch boundaries in `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md` are followed if reload is needed.
- The worker confirms whether the single-login-system rebuild is required before any live proof attempt.
- The worker confirms whether the binary flow is implementable as written or names the exact condition that needs Luke/Rep adjustment.
- No repeated phone/SMS attempts occurred.
- No Amazon security bypass occurred.

## Retest
- retest_command: run the approved focused F login/session tests and read-only F MOT from the underlying F packets.

## Stop Condition
Stop immediately if Amazon requires a human/security decision, MFA/manual challenge, repeated phone/SMS attempt, more than one controller-mode promotion, browser/session mutation outside approved path, credential/cookie/OTP handling, queue edit, output deletion, price change, Sheet/database action, or business judgement.
