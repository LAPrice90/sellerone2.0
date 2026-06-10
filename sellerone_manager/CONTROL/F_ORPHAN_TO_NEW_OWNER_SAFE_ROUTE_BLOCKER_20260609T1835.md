# F Orphan To New Owner Safe Route Blocker - 2026-06-09 18:35 UK

Job: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`
Worker role: SellerOne F Worker
Mode: F-only safety route decision

## Result

Exact blocker. F is not finished and is not parked-and-moving.

The earlier orphan-child shape changed while this worker was checking it. The old owner PID `14368` and child PID `29196` were no longer visible, but F status files then showed a new FPM130 owner and a new F061 child:

- FPM130 owner PID: `2972`
- F061 child PID: `25780`
- child parent: PID `2972`
- supplier: `td_synnex`
- manager mode: `Login Window Open`
- auth state: `LOGIN_REQUIRED`
- browser mode/visibility: visible
- live-cycle status: `running`
- live-cycle action: `resume_f061_active_run`
- login mode: `login_mode=1`

This worker did not start PID `2972` or child PID `25780`.

## What Was Checked

Process and ownership:

- old owner PID `14368`: no longer visible
- old child PID `29196`: no longer visible
- new owner PID `2972`: visible
- new child PID `25780`: visible
- no `F_restart_drain.ready` marker exists
- `live_cycle.lock` points to owner PID `2972`
- shared maintenance markers read no content

Controller proof:

- `f_login_controller_report_latest.md` updated at `2026-06-09T17:34:22Z`
- latest result: `seller_central_blocked`
- status: `disabled`
- reason: `normal_scan_only`
- blocker: `normal_scan_only`
- Dashboard Yes/No: not visible yet

Login-mode request:

- `f061_login_mode.requested` exists
- status: `holding`
- last observed UTC: `2026-06-09T17:33:07Z`
- last status note: `selected_login_rows=23;selected_bbp_login_rows=23;hold_seconds=60`

Logged-out continuation:

- `td_synnex`: 23 `login_backtrack_pending` rows
- `td_synnex`: 38 `pending` rows
- TD Synnex run state remains `run_status=running`, `pending_rows=61`, `held_rows=0`
- no `seller_central_second_check_hold` event was found in the checked live event tail
- no return path showing TD Synnex held and next supplier moved was proved

## What Failed

There is no safe F-only handoff/reload action available from this worker lane right now.

The old orphan-child state has been replaced by a new active F owner/child, but that new active child is still alive and has not produced either accepted finish condition:

- Dashboard Yes/No through the single controller: not proved
- logged-out continuation with TD Synnex held and next safe file moved: not proved

Because no `F_restart_drain.ready` marker exists and child PID `25780` is still active, reloading the owner now would require either a blind stop/kill or starting another owner. Both are outside this worker's approval.

## Exact Blocker

Active F child PID `25780` is still alive under owner PID `2972`, with no drain-ready marker, while the controller remains blocked at `normal_scan_only`.

The only safe route available without elevated/user action is passive wait for one of these exact proof conditions:

- child PID `25780` exits naturally and no F child remains, or
- `F_restart_drain.ready` appears for owner PID `2972`, or
- live-cycle status changes to an accepted final state showing either Dashboard Yes/No proved or TD Synnex held for second-check with next safe supplier moved.

Until one of those happens, this worker must not trigger a reload, create a second owner, or kill the child.

## Safety Confirmation

- No blind kill was attempted.
- No second F owner or child was started by this worker.
- No normal F business scanning was started by this worker.
- No Seller Central action was taken by this worker.
- No SMS, phone, or code was requested by this worker.
- No Amazon security bypass occurred.
- No separate Chrome workaround occurred.
- No OTP, cookie, token, credential, or raw secret was exposed or stored.
- No price change, Sheet write, DB alignment, output deletion, purchase, receiving, or send-to-Amazon action occurred.
- No Task Scheduler action was taken by this worker.
- No A/B/E/H/O widening occurred.

## Safest Proposed Fix

Operations should monitor only until child PID `25780` exits naturally or owner PID `2972` writes `F_restart_drain.ready`. If neither occurs within the approved emergency monitoring window, the next step requires a named Luke/Operations decision for a targeted F-only stop method for PID `25780` and owner PID `2972`, with proof that no softer method remains.
