# HARD-EXIT ROOT CAUSE STATUS

## What was changed
- `scripts/cycles/run_H_pricing_cycle.py`: non-int `SystemExit` in inline module runner now returns non-zero (`1`) instead of `0`.
- `run_H_cycle.bat`: default guard wrapper enabled, pilot mode default changed to `subprocess`, scheduler vars made override-friendly (`if not defined ...`), mode echo includes `H_HEALTH_RUN_INLINE`.
- `scripts/cycles/run_H_pricing_cycle_guarded.py`: heartbeat includes explicit `MODE=...`; `os._exit` marker logging enabled in all modes.

## Verification snapshot
- `hard_exit_verify_after.csv` captured mixed results: some clean EXIT_OK runs, some runs with missing exit marker and stale lock.

### Evidence lines
- 2026-02-23T16:57:47Z phase1 pilot_step child_started pid=2256 run_id=20260223T165644Z
- 2026-02-23T16:58:07Z cycle_start run_id=20260223T165807Z pid=10268 ppid=12560 phase1_pilot=1 run_once=1 loop_sleep_seconds=1.00 h_split_mode_requested=shadow h_split_mode_effective=shadow phase1_pilot_mode=subprocess phase1_intel_mode=inline phase1_publish_mode=inline bisect_force_inline=0 stage_snapshot_refresh=1 stage_item_offers=1 stage_phase1_pilot=1 stage_phase1_intel=1 stage_phase1_publish=1
- heartbeat_tail_last_line: STAGES snapshot_refresh=1 item_offers=1 phase1_pilot=1 phase1_intel=1 phase1_publish=1

## Current conclusion
- False-success mapping bug is fixed (`SystemExit` string no longer maps to rc=0).
- Pilot is now defaulted to subprocess mode in launcher.
- Hard-exit condition is reduced but not fully eliminated in direct guarded runs; lock leftovers can still appear when process ends without heartbeat exit marker.

## Next technical step (root-cause phase 2)
- Add process-level crash sentinel in `run_H_pricing_cycle.py` startup and ensure lock write includes generation token so orphan lock from prior generation cannot be mistaken for current owner.
- Add explicit parent-child watchdog for subprocess pilot mode: if parent exits unexpectedly, child writes terminal marker and parent launcher treats as non-zero.
- Re-run isolated matrix with background H launcher disabled during test window.

## Launcher guard proof
- cmd /c run_H_cycle.bat one-shot with guard returned BAT_RC=98 when heartbeat exit marker was missing.
- Evidence line: [23/02/2026 16:59:45.80] H-cycle launcher detected missing heartbeat exit marker - forcing exit 98
