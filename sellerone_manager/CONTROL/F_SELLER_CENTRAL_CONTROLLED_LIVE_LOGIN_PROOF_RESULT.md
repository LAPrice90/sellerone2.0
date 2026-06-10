# F Seller Central Controlled Live Login Proof Result

Observed UTC: 2026-06-09T15:40:32Z
Job: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`
Worker role: SellerOne F Worker
Proof window: `CONTROL/F_CONTROLLED_LIVE_LOGIN_PROOF_WINDOW.md`
Approved packet: `tasks/approved/MGR_F_SELLER_CENTRAL_SAFE_LOGIN_TODAY.md`

## Result

Safely blocked after one controlled live proof window.

Dashboard Yes/No: No - not proved.

Logged-out continuation: No - not proved.

Exact blocker:

- the rebuilt single F login controller was active, but Seller Central recovery stayed in `normal_scan_only`
- latest controller reason was `attempt_mode_not_enabled`
- no Seller Central login attempt occurred
- no SMS, phone, or code attempt occurred
- TD Synnex stayed first in the active queue with 67 rows
- no proof showed TD Synnex held for later Seller Central second-checks and moved to the next safe file
- a new FPM130 owner PID `14368` appeared after the proof owner PID `29344` exited, so the worker stopped instead of starting or widening another proof attempt

## Owner And Child State

Before proof:

- stale F child PID `14740`: not present
- A maintenance locks: clear
- prior F-only visible-login marker was preserved as `out/systems/F/price_list_manager/live/f061_visible_login.requested.held_for_proof_20260609T162058`
- no normal business scan was intentionally started by this worker

Proof owner:

- FPM130 owner PID: `29344`
- F061 child PID: `13732`
- scanner-owned browser path: `C:\Users\Luke\AppData\Local\Chrome_UC136`
- scanner-owned profile: `Profile 2`
- child mode: visible scanner-owned path

After proof window:

- proof owner PID `29344` exited
- `live_cycle.lock` was replaced by new FPM130 owner PID `14368`
- supervisor log says `action=restart_manager reason=manager_process_missing launched_pid=14368`
- supervisor state says `alive_no_progress`
- stale child status file still names PID `13732`, but process scan no longer showed an active F061 child under that PID
- worker did not start another owner and did not kill any process

## Controller And Dashboard Proof

Single controller route confirmed:

- controller: `F_LOGIN_CONTROLLER_REWRITE_V1`
- controller report path: `out/systems/F/price_list_manager/live/f_login_controller_report_latest.md`
- controller state path: `out/systems/F/price_list_manager/live/f_login_controller_state.json`

Latest controller result:

- status: `disabled`
- reason: `normal_scan_only`
- blocker: `normal_scan_only`
- notes: `login_attempt_control_reason=attempt_mode_not_enabled`
- Dashboard Yes/No: not visible yet
- attempted flag: `0`
- succeeded flag: `0`

This means the proof did not reach Seller Central Dashboard Yes/No.

## Logged-Out Continuation Proof

Logged-out continuation did not pass.

Evidence:

- active queue still begins with `td_synnex`
- active queue grouped rows after the proof check:
  - `td_synnex`: 67
  - `stax`: 37
  - `heo`: 25
  - `shure_cosmetics`: 19
  - `bliss_distribution`: 1
- latest F child scan kept recording `Seller Central eligibility login required; BBP account login alone is not enough for dashboard yes/no`
- no proof row showed TD Synnex moved to a durable `held_for_login` or `second_check_after_login` file state
- no proof row showed the next safe file started after TD Synnex

## Tropicana Check

Tropicana supplier route exists:

- `scripts/flows/F/suppliers/tropicana_wholesale.py`

Tropicana June price-list file was not found in the current searched locations.

Found only:

- `C:\Users\Luke\Downloads\Tropicana_Wholesale_Investment_Proposition.pdf`
- `out/systems/F/price_list_manager/test_mode/tropicana_wholesale_source_20260519T102200Z_8cdcc58d1170_converted.csv`

Tropicana status: blocked - June price-list file not found in current searched locations; supplier route exists.

## Cooldown Or Manual Challenge

Cooldown/manual challenge state: none observed.

Amazon/security stop condition observed: none.

No captcha, passkey, authenticator-only prompt, account recovery, Amazon wait/try-later wording, or manual challenge was observed in this proof window.

## Safety Confirmation

- No Amazon security bypass occurred.
- No MFA disablement occurred.
- No repeated SMS, phone, or code attempt occurred.
- No SMS, phone, or code attempt occurred at all.
- No separate Chrome workaround occurred.
- No browser/profile/cookie manipulation occurred.
- No OTP, cookie, token, credential, or raw secret was stored or exposed.
- No prices were changed.
- No Google Sheets writes occurred.
- No Product DB or local DB alignment occurred.
- No purchase, receiving, or send-to-Amazon action occurred.
- No output deletion occurred.
- Task Scheduler was not touched by this worker.

## Safest Proposed Fix

Keep F marked not proved and not trusted live.

Next repair should fix the F controller handoff so a bounded F proof child receives the Seller Central attempt-mode gate only through the single controller, and add a real logged-out continuation path that holds TD Synnex for Seller Central second-checks and moves to the next safe queued file when login is unavailable.

Operations must handle the `AMZ Pricing Summary Hourly` restore/proof separately because Task Scheduler is outside this worker scope.

## Owner Handoff Continuation - 2026-06-09T16:12:30Z

Follow-up evidence note:

- `CONTROL/F_OWNER_HANDOFF_RELOAD_RESULT_20260609.md`

Continuation result: exact blocker.

F is drain-ready, but the F-only request marker is missing and the active maintenance marker is A-owned. The only identified helper clear route would remove the legacy global maintenance marker, so owner handoff/reload was not performed by this F worker.

## Current Owner Continuation - 2026-06-09T17:00:47Z

Follow-up evidence note:

- `CONTROL/F_CURRENT_OWNER_PROOF_CONTINUATION_RESULT_20260609.md`

Continuation result: exact blocker.

F owner PID `14368` and child PID `11480` are running on TD Synnex with `login_mode=1`, but the Seller Central controller still reports `normal_scan_only` and `attempt_mode_not_enabled`. Dashboard Yes/No is not proved, and logged-out continuation is not proved because TD Synnex remains the first active supplier and no held-for-second-check return path has been recorded.

## Repair-Ready Proof Routing Check - 2026-06-09T18:16 UK

Follow-up evidence note:

- `CONTROL/F_BOUNDED_PROOF_ROUTE_BLOCKER_20260609T1816.md`

Continuation result: exact blocker.

Repair is ready, but the new bounded proof window was not started because the safe F owner handoff/reload route is blocked by an active A-owned maintenance marker and live A process. F owner PID `14368` is drain-ready, but shared maintenance still says `requested_by=A`, `active_by=A`, PID `35868`, reason `A_cycle_run`, and process evidence shows PID `35868` plus A child PID `33460` still running. Starting another F owner, clearing the A marker, or modifying scheduler state would violate this worker packet.

## Current Bounded Proof Monitor - 2026-06-09T18:23 UK

Follow-up evidence note:

- `CONTROL/F_CURRENT_BOUNDED_PROOF_BLOCKER_20260609T1823.md`

Continuation result: exact blocker.

Operations cleared the A-owned maintenance blocker and the current F owner PID `14368` launched F061 child PID `29196` on TD Synnex with `login_mode=1`. The current proof child still wrote a fresh Seller Central controller row showing `normal_scan_only` / `attempt_mode_not_enabled`, with attempted flag `0` and succeeded flag `0`. Dashboard Yes/No was not proved. Logged-out continuation was also not proved because TD Synnex remained first with 61 pending/login-backtrack rows, `held_rows=0`, and no `seller_central_second_check_hold` return-path event. The likely cause is that owner PID `14368` predates the repair-only code change, so the repaired handoff is on disk but not loaded into this existing owner/child.

## Orphan To New Owner Safety Route - 2026-06-09T18:35 UK

Follow-up evidence note:

- `CONTROL/F_ORPHAN_TO_NEW_OWNER_SAFE_ROUTE_BLOCKER_20260609T1835.md`

Continuation result: exact blocker.

The old owner PID `14368` and child PID `29196` were no longer visible during the safety check, but live F status then showed a new owner PID `2972` and child PID `25780` on TD Synnex. This worker did not launch those processes. The new child wrote fresh controller evidence that still blocked at `normal_scan_only`, and TD Synnex remained unheld with `pending_rows=61`, `held_rows=0`. No `F_restart_drain.ready` marker exists for owner PID `2972`, so there is no safe F-only reload trigger while child PID `25780` remains active. The only safe route is passive wait for natural child exit, a drain-ready marker, or an accepted final proof state.

## Safe Proof Precondition Check - 2026-06-09T21:25 UK

Follow-up evidence note:

- `CONTROL/F_SAFE_PROOF_PRECONDITION_BLOCKER_20260609T2125.md`

Continuation result: exact blocker.

F is not finished and not parked-and-moving. A/hourly blocking was clear enough to check F, but F already had live-cycle owner PID `13164` holding `live_cycle.lock`. F061 manager mode showed idle with `pid=0`, but the live owner was blocked in `apply_next_batch`; TD Synnex had one row marked `second_check_after_login`, while TD run state still showed `pending_rows=1`, `held_rows=0`, and the next file `clf` was blocked before starting. Starting another F owner would violate the no-second-owner boundary.
