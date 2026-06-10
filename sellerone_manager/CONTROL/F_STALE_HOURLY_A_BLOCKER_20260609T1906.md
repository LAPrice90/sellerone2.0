# F Stale Hourly A Blocker - 2026-06-09 19:06 UK

## Status

F is not finished and not parked-and-moving.

F is drain-ready and waiting for the shared maintenance gate to clear.

## F Evidence

- F owner PID: `2972`
- F child PID: none visible
- F061 mode: `Idle`
- Drain marker: `F_restart_drain.ready`
- Drain marker content: `launcher_pid=2972|utc=2026-06-09T18:06:19Z|state=drain_wait`
- Seller Central proof: not run
- Logged-out parked-and-moving proof: not run

## Active Blocker

`AMZ Pricing Summary Hourly` launched a full A run at about `2026-06-09 18:52 UK` and still owns shared maintenance at `2026-06-09 19:06 UK`.

Evidence:

- A hourly PID: `36612`
- Process: `python`
- Start time: `2026-06-09 18:52:02 UK`
- CPU observed: `1.203125`
- Maintenance requested marker: `requested_by=A|pid=36612|ts=2026-06-09T17:52:04Z|reason=A_cycle_run|request_id=A_20260609T175204Z_36612_40972244`
- Maintenance active marker: `active_by=A|pid=36612|ts=2026-06-09T17:52:30Z|reason=A_cycle_run|request_id=A_20260609T175204Z_36612_40972244`

Scheduler state:

- `AMZ Pricing Summary Hourly`: Disabled, Status Running, Next Run Time `N/A`
- This means the next hourly trigger is held, but the already-running A instance remains active.
- Daily `AMZ Pricing Summary` was not touched.

## What Operations Attempted

- Verified F drain-ready state.
- Verified A hourly process and shared maintenance ownership.
- Disabled only the hourly scheduler trigger under the approved bounded F emergency route.
- Did not stop the already-running A process.
- Did not start F handoff/reload while A owns active maintenance.

## What Failed

F handoff/reload cannot safely start because shared maintenance is still A-owned by PID `36612`.

## Safest Proposed Fix

Rep/Luke decision route:

1. If A PID `36612` clears naturally, immediately route the approved F owner handoff/reload from drain-ready owner PID `2972`.
2. If A PID `36612` remains stuck, approve a named A-hourly recovery action for PID `36612`, with exact stop method, proof that only the hourly A instance is targeted, and post-action maintenance-clear proof.
3. After F recovery/proof, restore and prove `AMZ Pricing Summary Hourly`, or keep it named as blocked before `2026-06-10 07:00 UK`.

## Boundaries Preserved

No price changes, Sheet writes, database alignment, output deletion, purchase, receiving, send-to-Amazon action, Amazon security bypass, permanent scheduler redesign, second F owner, F reload, Seller Central proof attempt, or blind process kill occurred.

## Follow-Up - 2026-06-09 19:20 UK

The stale A hourly blocker cleared naturally.

- A hourly PID `36612` was no longer visible.
- Shared maintenance requested marker returned no content.
- Shared maintenance active marker returned no content.
- F moved from drain-ready into a live login window under child PID `36164`.

This does not finish F. Dashboard proof or logged-out parked-and-moving proof is still required.

`AMZ Pricing Summary Hourly` remains intentionally held for the F proof window and must be restored/proved after F proof finishes or blocks.

## Restore Proof - 2026-06-09 19:23 UK

The F proof window blocked on `normal_scan_only`, so `AMZ Pricing Summary Hourly` was restored.

Proof:

- `AMZ Pricing Summary Hourly`: Enabled, Ready, next run `2026-06-09 19:52`
- Daily `AMZ Pricing Summary`: Enabled, Ready, next run `2026-06-10 06:00`
- Shared maintenance requested/active markers returned no content
