# F Single Login System Rebuild

## Manager Authority
- task_id: MGR_F_SINGLE_LOGIN_SYSTEM_REBUILD
- job_ref: F-SINGLE-LOGIN-SYSTEM-REBUILD
- flow: F
- task_type: urgent_code_rebuild
- status: proved
- authority: luke_requested_single_f_login_system_2026-06-09
- priority: urgent
- luke_action_required: 0

## Plain English
F must stop using three competing login systems.

The worker must rebuild F around one login controller, one Dashboard Yes/No decision, one scanner-owned browser/session path, and a non-stop price-file flow that parks login-required second checks instead of freezing the whole cycle.

## Required Plan
- Read `CONTROL/F_SINGLE_LOGIN_SYSTEM_FINAL_PLAN.md`.
- Read `CONTROL/F_SINGLE_LOGIN_SYSTEM_FINAL_FLOW.mmd`.
- Read `CONTROL/F_SINGLE_LOGIN_SYSTEM_RISK_REDUCTION_GATES.md`.
- Treat the existing F login controller, cooldown policy, browser-session durability, and safe-login-today packets as supporting context.

## Allowed Work
- inspect F login entry points
- identify old scanner login, UI login button login, and auto-login ownership
- create a redacted containment audit showing every F login owner and browser-opening route
- create or update one redacted F login state dashboard/view
- design or implement one controller-owned route if inside existing approved F code boundaries
- add a controller-level login-attempt freeze while duplicate owners are being contained
- make UI login button request the controller rather than owning login
- make old scanner login route call the controller or retire it inside the approved boundary
- make auto-login call the controller or retire it inside the approved boundary
- implement logged-out continuation if inside approved F code boundaries
- park login-required rows/files for second check after login
- prove logged-out price-file continuation with focused tests before any live login proof
- design or implement the controlled human-assist route through the single controller
- run focused local tests
- run read-only F MOT
- write redacted proof

## Forbidden Work
- no Amazon security bypass
- no MFA disablement
- no repeated SMS or phone requests
- no separate Chrome workaround
- no OTP, cookie, token, credential, or raw secret storage
- no output deletion
- no price changes
- no Google Sheets writes
- no Product DB or local DB alignment
- no purchase, receiving, or send-to-Amazon
- no widening into A, B, E, H, or O
- no F runtime pause/restart unless a named approved maintenance packet says exactly what to pause, how to restart, and how to prove health

## Acceptance Proof
- risk gates in `CONTROL/F_SINGLE_LOGIN_SYSTEM_RISK_REDUCTION_GATES.md` are satisfied or a precise blocker is recorded
- one login controller owns every F login attempt
- UI login button routes through the controller
- old scanner login route no longer races the controller
- auto-login no longer races the controller
- Dashboard Yes/No is the first login decision
- a redacted F login state dashboard/view exists
- login attempts are frozen until the single controller owns the route
- logged-out mode continues price-file scanning
- login-required rows are parked for second check
- held files resume automatically when login returns
- focused logged-out continuation tests pass before live login proof
- no repeated SMS/phone attempts occur
- no Amazon security bypass occurs
- focused tests pass
- read-only F MOT reports truthful state

## Retest
- retest_command: run focused F login/session/price-file continuation tests, then run read-only F MOT.

## Stop Condition
Stop immediately if the work requires Amazon security bypass, MFA disablement, repeated SMS/phone attempt, separate Chrome workaround, credential/cookie/OTP handling, output deletion, price change, Sheet/database action, purchase/receiving/send-to-Amazon, or business judgement.
