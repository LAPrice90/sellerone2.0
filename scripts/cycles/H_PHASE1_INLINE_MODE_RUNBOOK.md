# H Phase1 Inline Mode Runbook

## Default behavior
- `H_PHASE1_PILOT_MODE=inline`
- `H_PHASE1_INTEL_MODE=inline`
- `H_PHASE1_PUBLISH_MODE=inline`

If a mode variable is unset or invalid, it falls back to `inline`.

## How to toggle modes
- Inline default (recommended):
  - `set H_PHASE1_PILOT_MODE=inline`
  - `set H_PHASE1_INTEL_MODE=inline`
  - `set H_PHASE1_PUBLISH_MODE=inline`
- Roll back pilot only to subprocess:
  - `set H_PHASE1_PILOT_MODE=subprocess`
- Roll back all three to subprocess:
  - `set H_PHASE1_PILOT_MODE=subprocess`
  - `set H_PHASE1_INTEL_MODE=subprocess`
  - `set H_PHASE1_PUBLISH_MODE=subprocess`

## Acceptance test
1. `set H_RUN_ONCE=1`
2. Run `run_H_cycle.bat`
3. Confirm `out/systems/H/live/H_cycle.log` shows:
   - `phase1_pilot_mode=inline` at cycle start
   - `phase1 pilot_step inline_start`
   - `phase1 pilot_step inline_end rc=...`
   - If intel and publish run that cycle:
     - `phase1 daily_intel alignment inline_start/inline_end`
     - `phase1 observation_publish inline_start/inline_end`
4. Confirm `out/systems/H/live/H_pricing_cycle.HEARTBEAT.txt` ends with:
   - `EXIT_OK ...`
5. Optional rollback check:
   - Set `H_PHASE1_PILOT_MODE=subprocess`
   - Re-run and confirm `phase1 pilot_step child_started pid=...` appears again.

## Stage Bisect Controls
- Stage env toggles (default `1`):
  - `H_STAGE_SNAPSHOT_REFRESH`
  - `H_STAGE_ITEM_OFFERS`
  - `H_STAGE_PHASE1_PILOT`
  - `H_STAGE_PHASE1_INTEL`
  - `H_STAGE_PHASE1_PUBLISH`
- Force inline during bisect:
  - `set H_BISECT_FORCE_INLINE=1`
- Optional CLI overrides:
  - `--only-stage <snapshot_refresh|item_offers|phase1_pilot|phase1_intel|phase1_publish>`
  - `--skip-stage <name>` (repeatable)

## Bisect Artifacts
- Stage markers:
  - `out/systems/H/live/STAGE_ENTER.<stage>.txt`
  - `out/systems/H/live/STAGE_EXIT.<stage>.txt`
- Process trees:
  - `out/systems/H/live/process_tree.<stage>.enter.txt`
  - `out/systems/H/live/process_tree.<stage>.exit.txt`

## Crash Recurrence Playbook (2026-03-11)

Use this when H "dies again" after reboot/shutdown/power events.

### What was fixed
- Root-cause code fixes were applied for:
  - restart-drain loop crash (`state` could be referenced before assignment)
  - stale restart-control drain handling (controller could leave drain active)
  - safer phase1 pilot subprocess handling (result-file-first, not stdout dependency)

### First checks (2 minutes)
1. Confirm launcher and runtime markers:
   - `out/systems/H/live/H_launcher.lock`
   - `out/systems/H/live/H_runtime_status.json`
   - `out/systems/H/live/H_pricing_cycle.EXIT_STATUS.txt`
2. Check if H is repeatedly exiting early:
   - search `out/systems/H/live/H_cycle.log` for:
     - `restart_drain requested - boundary reached before new cycle start`
     - `FINALIZE_BLOCKED_NO_PUBLISH`
3. Check run alignment:
   - `out/systems/H/live/H_run_in_progress.txt`
   - `out/systems/H/live/H_last_finalized_run_id.txt`
   - `out/systems/H/live/H_cycle_last_publish_run_id.txt`

### If blocked by stale run marker
- Use the archive tool for the specific stuck run id (safe path):
  - `python scripts/tools/archive_failed_H_run.py --run-id <RUN_ID> --archive-reason <SHORT_REASON>`
- Do not mass-delete logs or lock directories.

### If blocked by stale restart drain
1. Inspect restart control artifacts:
   - `out/locks/restart_control/restart_controller.latest.txt`
   - `out/locks/restart_control/restart_eval.latest.txt`
2. Confirm no active maintenance intent:
   - `out/locks/maintenance.requested`
   - `out/locks/maintenance.active`
   - `out/locks/maintenance.ready`
3. If all maintenance files are absent, but restart drain still repeats, treat as stale control artifact and rotate safely between runs.

### Parent-loss evidence capture
- Use these files before changing code:
  - `out/systems/H/live/H_parent_trace.log`
  - `out/systems/H/live/H_ATEXIT_TRACE.log`
  - `out/systems/H/live/H_core_parent_exit_capture.latest.json`
- If Python vanishes with no traceback, check Windows Event Viewer around the exact UTC failure time.

### Success criteria after any repair
- Observe 3 clean cycles in a row after the repair:
  - each cycle reaches publish `status=ok`
  - each cycle reaches `from=published to=finalized`
  - `H_cycle_last_publish_run_id.txt` matches `H_last_finalized_run_id.txt`
- Background operation remains running after the third clean cycle.
