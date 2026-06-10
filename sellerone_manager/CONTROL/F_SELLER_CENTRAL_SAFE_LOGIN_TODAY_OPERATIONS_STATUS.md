# F Seller Central Safe Login Today - Operations Status

Updated: 2026-06-09 14:45 UK
Role: Operations
Job: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`

## Current Status

F is not trusted live.

Operations has placed the approved F-only maintenance stop request so normal business scanning should drain and stop before the repair/proof path continues.

Request file:

- `out/systems/F/price_list_manager/live/f061_visible_login.requested`

Request details:

- `requested_by=Operations`
- `reason=F_SINGLE_LOGIN_CONTROLLER_STATUS_REPAIR_TD_SYNNEX_STAGNATION`
- `action=reload`
- `exit_after_drain=1`
- `target=F_price_list_scanner_owner_only`
- `normal_business_scanning_allowed=0`

## Active Business Symptom

Luke states F has been stuck at the end of the TD Synnex price file for days.

Operations records this as the active failure symptom:

- TD Synnex end-of-file stagnation is the business failure.
- Fresh status-file updates do not equal real progress.
- `LOGGED_IN`, `Catching Up`, and heartbeat/timestamp refresh alone must not be used to call F healthy.
- BBP authentication must be kept separate from Seller Central Dashboard Yes/No proof.

## Latest Observed Runtime Signal

Latest observed files still showed misleading optimism:

- `f061_manager_mode_state.txt` showed `mode=Catching Up` and `auth_state=LOGGED_IN`.
- `fpm_live_supervisor_state.txt` showed `alive_no_progress`.
- `f061_child_stderr.log` showed Seller Central recovery disabled because the child was still in `normal_scan_only`.
- `f061_child_stderr.log` also showed BBP auth activity, which is not Seller Central Dashboard proof.

Plain English: F was still refreshing signs of activity, but it had not proved the actual Seller Central outcome Luke needs.

## Maintenance Boundary

Approved authority used:

- `CONTROL/F_CONTROLLED_OWNER_RELOAD_MAINTENANCE_APPROVAL.md`
- `CONTROL/SO21_BUSINESS_RUNTIME_MAINTENANCE_AUTHORITY.md`
- `CONTROL/ARCHITECTURE_DECISIONS.md` ADR-0023

Operations used the soft maintenance request path only. Operations did not perform a blind kill, create a second F owner, open a separate browser path, attempt Seller Central login, request SMS/phone/code, bypass Amazon security, change prices, write Sheets, align databases, delete outputs, or widen into other flows.

## Repair Owner

Repair remains under the active F packet:

- `tasks/approved/MGR_F_SELLER_CENTRAL_SAFE_LOGIN_TODAY.md`
- Worker thread: `019eac28-6bb2-7642-9e04-87503c5f2e68`

Worker repair must focus on the single-login controller/status model before normal F runtime resumes.

Required repair outcomes:

- one clear binary Seller Central login flow
- no false `LOGGED_IN` wording unless Seller Central Dashboard Yes/No proof has passed
- BBP auth state separated from Seller Central auth state
- UI login, old scanner login, and auto-login must not compete
- scanner must hold or park login-required supplier work instead of stagnating or sending bad review work

## Restart Proof Required

F must not return to normal business scanning until a bounded proof window shows one of these:

- TD Synnex moves past the stuck end-of-file point, or
- Seller Central remains unavailable but F parks/holds TD Synnex login-required work cleanly, moves to the next price file, and records a return path for later second-check.

Dashboard Yes/No proof remains required before any `logged in` or `healthy live` language is used.

## Current Stop State

The stop request has been placed. At the time of this note, the active manager/child had not yet acknowledged `F_restart_drain.ready`, so Operations is monitoring the soft drain boundary rather than forcing a kill.

Latest read:

- manager PID observed: `16664`
- child PID observed: `14740`
- child supplier: `td_synnex`
- supervisor state: `alive_no_progress`
- last scanner progress: `2026-06-09T13:16:48Z`
- drain ready marker: not present

If the drain is not acknowledged at the next safe boundary, record that as a maintenance-stop blocker with the active owner PID and safest proposed fix.

## Operations Pass - 2026-06-09 14:47 UK

Outcome: next approved packet assigned to Worker and drain still pending.

- Worker thread `019eac28-6bb2-7642-9e04-87503c5f2e68` is active on this packet.
- F-only stop request remains present.
- Drain ready marker remains not present.
- Latest child status still shows supplier `td_synnex`, manager mode `Catching Up`, and fresh heartbeat/output timestamps.
- Supervisor still reports `alive_no_progress`.
- Operations does not treat these fresh timestamps as real progress because Luke's active symptom is TD Synnex end-of-file stagnation.

Next Operations condition: wait for Worker result or `F_restart_drain.ready`; if neither appears after the active child's safe boundary, record a maintenance-stop blocker.

## Operations Pass - 2026-06-09 14:53 UK

Outcome: real blocker recorded.

Related blocker record:

- `CONTROL/F_MAINTENANCE_STOP_DRAIN_BLOCKER.md`

Plain-English Rep status:

- Why the work is slow: F accepted the maintenance request at manager level, but the old TD Synnex scanner child did not reach a clean drain marker. The child is stale and Windows denied the targeted stop attempt.
- Whether F is actually stopped: F is not normal-running, but it is not fully stopped either. It is paused at supervisor/manager level and still half-alive through child PID `14740` plus browser/driver descendants.
- What allows the next Seller Central proof attempt: the stale child must be gone, repair must be ready, one F owner route must be confirmed, and a bounded proof window must prove Dashboard Yes/No or clean logged-out parking/hold behavior that moves past the TD Synnex stuck point.
- Expected next checkpoint: Worker result from thread `019eac28-6bb2-7642-9e04-87503c5f2e68`, or confirmation that PID `14740` has exited. If PID `14740` remains stuck after the Worker result, Rep/Luke need an elevated Windows/admin-level F-only stop or PC-level recovery window decision.

Current machine-level blocker:

- targeted stop attempted for PID `14740`
- Windows returned `Access is denied`
- global maintenance request is also currently A-owned: `requested_by=A`, `reason=A_cycle_run`

Operations did not start a second owner, did not restart normal F scanning, did not attempt Seller Central login, and did not touch Amazon security, prices, Sheets, databases, outputs, purchase, receiving, or send-to-Amazon.
