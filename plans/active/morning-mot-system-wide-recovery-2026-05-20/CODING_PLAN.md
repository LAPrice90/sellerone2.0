# Morning MOT System-Wide Recovery Plan

## Goal
Build an executable morning MOT system that checks A, B, E, H, and F early enough to catch post-restart and post-A failures, then starts safe recovery actions for stale runtime owners.

## Current Phase
- Phase: implementation and isolated proof
- Started UTC: 2026-05-20T13:05:00Z

## Allowed Files
- `scripts/tools/morning_mot_system.py`
- `tests/test_morning_mot_system.py`
- `run_morning_mot_system.bat`
- `project_control/MORNING_MOT_CHECKLIST.md`
- `project_control/OUTPUT_SCHEMA_CHECKS.md`
- `project_control/DUE_CHECK_REGISTER.csv`
- This `CODING_PLAN.md`

## Runtime Safety Rules
- Do not run A automatically unless the command uses `--allow-a-repair`.
- Do not run overlapping B, H, or F workers directly.
- Repair B and H through their scheduler-owned entrypoints.
- Repair F through the F supervisor path, not a standalone browser login window.
- Record all repair attempts in `out/cycle_alerts/morning_mot_repair_actions.json`.

## Outputs
- `out/cycle_alerts/morning_mot_system_check.csv`
- `out/cycle_alerts/morning_mot_system_check.json`
- `out/cycle_alerts/morning_mot_repair_actions.json`

## Proof Plan
- Run focused unit tests for system classification and repair planning.
- Run the system MOT in live check mode.
- Run repair mode only if the live check produces a repair-safe runtime action.
- Verify output schema and row counts.

## Schedule Target
- Post-restart MOT: 02:35 local time.
- Post-A MOT: 06:30 local time.

## Success Criteria
- MOT output contains A, B, E, H, and F rows.
- Stale B/H/F produce repair actions that use normal owner entrypoints.
- A stale status is visible but not auto-run without explicit `--allow-a-repair`.
- Tests pass and live check writes schema-valid outputs.

## Timeout Rule
If repair proof is not confirmed inside the configured wait window, leave status as `repair_attempted_pending_proof` with the exact artifact to inspect next.

## First Scheduled Proof Follow-Up
- Trigger/time: 2026-05-21 06:45 BST, after `AMZ Morning MOT Post Restart` and `AMZ Morning MOT Post A` should both have run.
- Artifact to inspect: `out/cycle_alerts/morning_mot_system_check.csv`, `out/cycle_alerts/morning_mot_repair_actions.json`, and Windows Task Scheduler history for `AMZ Morning MOT Post Restart` / `AMZ Morning MOT Post A`.
- Success condition: latest MOT phase is `post_a`, A/E/B/H/F rows exist, runtime fail rows are 0, and any stale B/H/F/E repair action either succeeded or is absent because no repair was needed.
- Remediation path if it fails: run `run_morning_mot_system.bat --phase post_a --repair --proof-wait-seconds 30 --json`, inspect failed row `repair_action`, and fix the earliest owner path instead of masking the output.
