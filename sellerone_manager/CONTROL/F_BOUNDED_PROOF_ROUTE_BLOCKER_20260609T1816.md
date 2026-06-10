# F Bounded Proof Route Blocker - 2026-06-09 18:16 UK

Job: `F-SELLER-CENTRAL-SAFE-LOGIN-TODAY`
Worker role: SellerOne F Worker
Mode: bounded proof routing check only

## Result

Exact blocker. F is not finished and is not parked-and-moving.

The new bounded proof window was not started because the safe F owner handoff/reload route is blocked by an active A-owned maintenance marker and live A process.

## Evidence Checked

F owner state:

- FPM130 owner PID: `14368`
- `F_restart_drain.ready`: `launcher_pid=14368|state=drain_wait`
- `live_cycle.lock`: `pid=14368|owner=FPM130_live_cycle`
- `live_cycle_status.csv`: `state=drain_wait`, `active_supplier_id=td_synnex`, `pending_rows=61`, `last_action=restart_drain`, `drain_ready=1`

F061 child state:

- `f061_child_status.txt` still names PID `11480`, supplier `td_synnex`, manager mode `Seller Central Proof Required`
- process check found no active PID `11480`

Single controller state:

- controller: `F_LOGIN_CONTROLLER_REWRITE_V1`
- Dashboard Yes/No: not proved
- latest controller state still shows historical blocker `normal_scan_only` / `attempt_mode_not_enabled`
- the repair for this blocker is present, but it has not yet been loaded by a new safe F proof child

A maintenance state:

- `maintenance.requested`: `requested_by=A`, PID `35868`, reason `A_cycle_run`
- `maintenance.active`: `active_by=A`, PID `35868`, reason `A_cycle_run`
- process check found PID `35868` running `scripts/cycles/run_A_all.py`
- process check found A child PID `33460` running `scripts/flows/A/A016_refresh_phase1_daily_intel.py --mode full_universe`

## Why This Blocks The Approved F Proof Route

The approved F route allows only the existing F owner handoff/reload path, no second owner, no normal business scanning restart, and no scheduler or cross-flow action by this worker.

Because A currently owns the shared maintenance marker and has a live A process under that marker, this F worker cannot safely clear, replace, or reuse the shared maintenance marker to complete the F handoff/reload. Doing that would widen into A and risk cross-flow collision.

Starting another F owner would violate the no-second-owner rule.

## Proof Status

- Dashboard Yes/No proof: not attempted in this window
- Logged-out continuation proof: not attempted in this window
- TD Synnex held for second-check: not proved in this window
- next safe price file moved: not proved in this window

## Safety Confirmation

- No live F proof run was started.
- No normal F business scanning was restarted.
- No second F owner was created.
- No Task Scheduler change was made by this worker.
- No A marker was cleared or modified by this worker.
- No Amazon security bypass occurred.
- No repeated SMS, phone, or code attempt occurred.
- No separate Chrome workaround occurred.
- No OTP, cookie, token, credential, or raw secret was exposed or stored.
- No price change, Sheet write, DB alignment, output deletion, purchase, receiving, or send-to-Amazon action occurred.

## Safest Proposed Fix

Operations should first finish or safely release the A-owned maintenance run and prove the shared maintenance marker is clear. Then reroute one bounded F proof window through the existing F owner handoff/reload path so the repaired controller handoff can load into the next scanner-owned F061 proof child.
