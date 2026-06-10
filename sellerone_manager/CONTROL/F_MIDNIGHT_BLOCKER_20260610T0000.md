# F Midnight Blocker - 2026-06-10 00:00 UK

Owner: Operations
Status: exact hard blocker recorded

## Outcome

F is not finished and not parked-and-moving at the midnight deadline.

## Exact F Blocker

- PID `25928` is alive as `python` and owns `live_cycle.lock`.
- `live_cycle.lock` says `pid=25928`, `owner=FPM130_live_cycle`, `start=2026-06-09T22:18:27Z`, and `heartbeat=2026-06-09T22:49:37Z`.
- `F_restart_drain.ready` is absent.
- F061 is `Idle` with `pid=0`.
- No F061 child PID is active.
- No fresh scanner row progress is present.
- `fpm_live_supervisor_state.txt` says `alive_no_progress`, last refreshed at `2026-06-09T22:46:22Z`.
- `live_cycle_status.csv` remains blocked at `apply_next_batch`.
- `f_login_controller_state.json` remains stale at `2026-06-09T18:29:17Z`.
- Controller reason remains `normal_scan_only` / `attempt_mode_not_enabled`.
- Dashboard Yes/No is not proved.
- Logged-out parked-and-moving is not proved.

## Scheduler And Maintenance State

- Shared maintenance requested/active marker files are clear.
- `AMZ Pricing Summary Hourly` remains Disabled for the F emergency window.
- Daily `AMZ Pricing Summary` remains Enabled/Ready for `2026-06-10 06:00 UK` and was not touched.

## Midnight Rule Now Active

- Do not start non-F workers.
- Keep only F controller/handoff repair, direct runtime recovery, or mandatory morning recovery moving.
- Do not create a second F owner while PID `25928` owns the live lock.

## 02:00 Restart Risk Record

Paused or held:

- `AMZ Pricing Summary Hourly` is intentionally Disabled for the F emergency window.

Must restart or be proved after the restart window:

- F runtime state must be checked from actual files and processes, not assumed.
- `AMZ Pricing Summary Hourly` must be restored/proved after F proof finishes or have a named blocker by `2026-06-10 07:00 UK`.
- Daily `AMZ Pricing Summary` must remain Enabled/Ready for the `2026-06-10 06:00 UK` run unless a fresh blocker is recorded.

Must not restart automatically:

- No non-F worker refill while F remains unfinished.
- No second F owner while PID `25928` owns `live_cycle.lock`.
- No protected business action.

Post-restart verification:

- Check PID/process state for the F owner named in `live_cycle.lock`.
- Check `F_restart_drain.ready`.
- Check `f061_manager_mode_state.txt`.
- Check `f_login_controller_state.json`.
- Check `live_cycle_status.csv`.
- Check Task Scheduler state for both `AMZ Pricing Summary` and `AMZ Pricing Summary Hourly`.

## Required Next Action

Continue bounded F controller/handoff repair only, so the next F child consumes the approved login attempt path or cleanly executes logged-out continuation.
