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

## Controlled Isolation Validation (SELLERONE-ARCH-RESET-005)

Use this when H is scheduler-owned and you need isolated guarded validation.

### Operator-safe entrypoints
- `run_H_isolation_status.bat`
- `run_H_isolation_pause.bat`
- `run_H_isolation_success.bat`
- `run_H_isolation_failure.bat`
- `run_H_isolation_resume.bat`

### Required safety model
- `pause` and `resume` require elevated shell (`Run as administrator`).
- `run-success` and `run-failure` fail closed unless all are true:
- task `AMZ H Cycle` is not running
- task `AMZ H Cycle` is disabled
- no active H owner process remains
- `out/locks/h_controlled_mode.active` exists
- stale lock reconciliation has completed (confirmed-dead lock artifacts are archived under `out/locks/archive` and removed)
- isolated run exits with explicit terminal truth in `H_run_state.json` or `H_worker_lifecycle.json`

### Sequence for isolated validation
1. Baseline status:
- run `run_H_isolation_status.bat`
2. Pause scheduler ownership (elevated):
- run `run_H_isolation_pause.bat`
3. Isolated guarded success path:
- run `run_H_isolation_success.bat`
4. Isolated guarded induced-failure path:
- run `run_H_isolation_failure.bat`
- failure injection mode is `--skip-stage phase1_publish`
5. Resume normal ownership (elevated):
- run `run_H_isolation_resume.bat`
6. Confirm post-resume status:
- run `run_H_isolation_status.bat`

### Main evidence files
- `out/systems/H/live/H_run_state.json`
- `out/systems/H/live/H_worker_lifecycle.json`
- `out/systems/H/live/H_runtime_status.json`
- `out/systems/H/live/H_pricing_cycle.EXIT_STATUS.txt`
- `out/systems/H/live/H_pricing_cycle.HEARTBEAT.txt`
- `out/systems/H/live/H_cycle.log`

## Owner Termination Audit Readiness (SELLERONE-ARCH-RESET-022)

Use this before the next failing isolated capture when provenance still reports `win32_process_disappearance_only`.

### Operator entrypoints
- `run_H_owner_audit_status.bat`
- `run_H_owner_audit_enable.bat` (requires elevated shell)
- `run_H_owner_audit_revert.bat` (requires elevated shell, optional)

### Required sequence
1. Check readiness:
- run `run_H_owner_audit_status.bat`
- confirm output includes:
  - `readiness.assessment.process_creation_success_enabled=true`
  - `readiness.assessment.process_termination_success_enabled=true`
  - `readiness.assessment.security_channel_readable=true`
  - `readiness.assessment.ready_for_owner_termination_capture=true`
2. If not ready, enable minimum policy (elevated):
- run `run_H_owner_audit_enable.bat`
3. Verify readiness again:
- run `run_H_owner_audit_status.bat`
4. Run failing isolated capture sequence for owner provenance.
5. Optional revert to pre-enable baseline (elevated):
- run `run_H_owner_audit_revert.bat`

### Baseline and reversibility
- Enable action writes baseline to:
  - `out/systems/H/live/H_owner_audit_policy_baseline.json`
- Revert action restores audit settings from that baseline file.

### Notes
- If `auditpol` query reports privilege or access errors, re-run from elevated shell.
- This step changes host audit policy only. It does not change H runtime behavior.

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
