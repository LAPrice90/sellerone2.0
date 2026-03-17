# Cycle Recovery Plan v1 (2026-02-25)

## Objective
Make B cycle resilient like a service:
- If python dies: auto-restart (BAT supervisor)
- If a step fails: log rc + stderr/stdout tail
- If anything crashes: write traceback to B_FATAL.txt
- Heartbeat always advances while alive (separate thread)
- A maintenance handoff uses: maintenance.requested -> maintenance.ready (never b_not_running unless truly dead)

## Current Facts
- A maintenance handoff has ended with b_not_running in recent runs.
- B has died during or just after starting B001_run_orders_to_sheet.py attempt 1.
- Lock has shown start==heartbeat in failure windows, indicating early process stop.
- No Windows Application Error entries in recent checks.

## Tasks for Codex (in order)

### Task 1 - Make run_B_cycle.bat a hard supervisor loop
- Ensure it restarts python forever on any exit code.
- Log exit code and timestamp each loop.
- Add a short sleep before restart.

### Task 2 - Add crash-proof logging in run_B_cycle.py
- Add sys.excepthook to write full traceback to:
  out/systems/B/live/B_FATAL.txt
  and append fatal summary to B_cycle.log.
- Add atexit hook that writes: B_EXIT rc=<rc>.
- Wrap main loop with try/except so fatal exceptions are logged and re-raised.

### Task 3 - Add heartbeat thread independent of subprocess waits
- Thread updates out/systems/B/live/B_cycle.lock heartbeat every few seconds.
- Thread stops cleanly on shutdown.

### Task 4 - Instrument B001 and B002 subprocess runs
- capture_output=True.
- On nonzero rc: log rc + stdout_tail + stderr_tail.
- Keep step timeouts to prevent infinite waits.

### Task 5 - A maintenance reliability
- Use canonical B lock only.
- PID + heartbeat freshness required for B running.
- Wait for maintenance.ready before proceeding.
- ENSURE_B_AFTER_A enabled by default.

## Evidence required after fixes
- Show BAT supervisor restarting B after forced taskkill.
- Show B_FATAL.txt produced on induced exception.
- Show heartbeats continue during long steps.
- Show B001 failure logs include stderr/stdout tails.
- Show A maintenance uses maintenance.ready, not b_not_running.
