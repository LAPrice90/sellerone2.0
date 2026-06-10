# Execution Batch 001

## Purpose
- Prepare the full pause, backup, and manifest stage before any SQL storage code changes.

## Scope Guardrails
- Only do planning, pause-check design, backup-manifest design, and backup runbook work.
- Do not pause live systems yet without an approved execution window.
- Do not change Google Sheets.
- Do not change local DB state.
- Do not migrate any runtime flow in this batch.
- Do not run A015 or other A scripts for proof unless explicitly requested.

## Files Allowed To Change
- `plans/active/sql-storage-migration-v1/*`
- Later implementation, after this batch is approved:
- `scripts/one_off/P003_build_sql_migration_backup_manifest.py` or equivalent dedicated manifest tool
- `tests/test_sql_migration_backup_manifest.py`

## Inputs To Read First
- `AGENTS.md`
- `CODEX.md`
- `plans/active/sql-storage-migration-v1/PLAN.md`
- `plans/active/sql-storage-migration-v1/CODING_PLAN.md`
- `project_control/ARCHITECTURE.md`
- `project_control/DATA_BLUEPRINT.md`
- `project_control/DATA_BLUEPRINT_REGISTRY.csv`
- `project_control/DATA_LINEAGE_REPORT.md`
- `project_control/FORCED_PROOF_WINDOWS.md`

## Tasks
### Task 1 - Pause Checklist
- Goal: define exact checks that prove every live system and API caller is stopped.
- Files: plan files first, later manifest tool.
- Notes: must include A, B, E, H, O, Feeder, API collection, home-time monitor, controlled restart controller, SP-API scripts, LWA token callers, and FX refreshers.

### Task 2 - Backup Bundle Design
- Goal: define what gets backed up and where.
- Files: plan files first, later manifest tool.
- Notes: include code, tests, config, data, out, reference, project_control, plans, batch files, and secrets policy metadata.

### Task 3 - Manifest Schema
- Goal: define manifest columns before implementation.
- Files: plan files first, later manifest tool.
- Notes: include path, category, owner_flow, size_bytes, mtime_utc, sha256, row_count when tabular, header_hash when tabular, and backup_bundle_id.

### Task 4 - Restore Drill Design
- Goal: define how to prove the backup can restore one dataset and one full flow bundle.
- Files: plan files first.
- Notes: restore test must use a scratch path, not live `out/` or `data/`.

## Tests
- Command: `python -m pytest tests/test_p003_build_sql_migration_backup_manifest.py tests/test_p002_plan_forced_proof_window.py`
- Expected result: focused backup-manifest tests pass, and the existing forced-proof helper test still passes.
- Result: passed 12 tests on 2026-04-28.
- Note: plain `pytest` hit the repo's existing import-path issue for `scripts.one_off`; `python -m pytest` works and also passes the older P002 test pattern.

## Monitoring Plan
- Live proof needed: yes, before actual backup execution.
- Forced proof window: user-approved full pause window.
- Artifacts to poll: process list, lock files, owner markers, log mtimes, backup manifest, backup summary.
- Poll cadence: immediate preflight, then every 2 minutes during the pause window.
- Success threshold: no active owner process, no protected artifact writes during quiet window, complete backup manifest produced.
- Timeout rule: park if any owner cannot be paused or any protected artifact keeps changing.
- Fallback if forced proof is blocked: document the active owner and wait for a safe pause window.
- Next phase after success: Batch 002 storage adapter and schema skeleton.
- Notification mode: interrupt only for blocked pause, new FAIL, contradictory evidence, or approval need.
- User interruption threshold: stopping a process would require destructive scope or unknown ownership.

## Proof Required
- Row counts: required for all CSVs listed in `DATA_BLUEPRINT_REGISTRY.csv` where file exists.
- Health rows: latest existing health files are read as evidence, not regenerated.
- Output files: backup manifest and backup summary.
- Notes: no storage migration begins until backup proof exists.

## Current Proof Notes
- Tool added: `scripts/one_off/P003_build_sql_migration_backup_manifest.py`
- Test added: `tests/test_p003_build_sql_migration_backup_manifest.py`
- Runbook added: `plans/active/sql-storage-migration-v1/RUNBOOK.md`
- Read-only smoke command: `python scripts/one_off/P003_build_sql_migration_backup_manifest.py --skip-process-scan --format text`
- Smoke result: `safe_to_start_backup=no`
- Smoke blockers:
- `lock_present:out/systems/B/live/B_cycle.lock:running`
- `lock_present:out/H_pricing_cycle.lock:running`
- `lock_present:out/systems/H/live/H_pricing_cycle.lock:running`
- Interpretation: full backup and SQL migration must not start until B/H ownership is paused or handed off and a quiet window passes.

## Pause Attempt 2026-04-28
- User approved proceeding with the full pause window.
- `AMZ Controlled Restart` scheduled task was disabled successfully.
- Disabling `AMZ Orders`, `AMZ H Cycle`, and `AMZ Pricing Summary` failed from this shell with `Access is denied`.
- B maintenance/drain marker was written to `out/locks/maintenance.requested`.
- B reached maintenance boundary and `out/locks/maintenance.ready` appeared.
- B worker lock cleared, but elevated B supervisor PID `16944` remains active and relaunches boundary-exit workers every few seconds.
- Home-time supervisor tree PID `24288` was stopped successfully, including monitor PID `24348`.
- Built-in H pause script failed because elevation is required.
- H active run `20260428T115413Z` finalized successfully at `2026-04-28T12:08:41Z`, but elevated H launcher PID `16528` remains active and relaunches children.
- Attempts to stop elevated B/H owners with `taskkill` and `Stop-Process` failed with `Access is denied`.
- Current blocker state from `P003`: `safe_to_start_backup=no`.
- No backup manifest was written and no SQL migration was started.

## Pause Attempt Follow-Up 2026-04-28T12:14:52Z
- User asked to proceed again.
- Recheck still showed B supervisor PID `16944`, H launcher PID `16528`, and enabled scheduled tasks.
- Attempted to launch the exact elevated pause commands through Windows UAC.
- UAC result: `The operation was canceled by the user.`
- Because full pause could not complete, rollback actions were applied:
- removed `out/locks/maintenance.requested` if present
- removed `out/locks/maintenance.ready` if present
- re-enabled `AMZ Controlled Restart`
- restarted `run_home_time_monitor_supervisor.bat`
- Post-rollback scheduled task state: `AMZ Orders`, `AMZ H Cycle`, `AMZ Pricing Summary`, and `AMZ Controlled Restart` are all enabled/ready.
- Post-rollback `P003` result: `safe_to_start_backup=no`
- Remaining blocker: full SQL migration backup still requires an elevated pause window.

## Successful Pause And Registry Backup 2026-04-28T12:37:25Z
- User approved running the elevated pause directly.
- Elevated command completed with exit code `0`.
- Disabled scheduled tasks:
- `AMZ Orders`
- `AMZ H Cycle`
- `AMZ Pricing Summary`
- `AMZ Controlled Restart`
- Stopped owner processes:
- B supervisor PID `16944`
- B worker PID `16936`
- H launcher PID `16528`
- H guarded wrapper PID `7000`
- H child PID `21076`
- home-time monitor PID `11516`
- home-time supervisor PID `12368`
- Archived stale dead-PID locks to `out/locks/archive/sql_migration_pause.20260428T123203Z.*`.
- Immediate pause check result: `safe_to_start_backup=yes`.
- 120-second quiet check result: `safe_to_start_backup=yes`.
- Registry backup manifest written:
- `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/manifest.csv`
- `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/summary.json`
- Manifest counts:
- `row_count=58`
- `existing_file_count=51`
- `missing_registry_target_count=7`
- `hash_ok_count=51`
- `scan_error_count=0`
- Copied registry files:
- `copied_file_count=51`
- `copied_total_bytes=68576776`
- Copy verification:
- `checked_hash_count=51`
- `mismatch_count=0`

## Completion Checklist
- [x] Scope held
- [x] Files changed only in allowed set
- [x] Pause checklist complete
- [x] Backup manifest schema complete
- [x] Restore drill design complete
- [x] User-approved execution window identified before any live pause
- [x] Elevated B/H owner shutdown completed
- [x] 120-second quiet check passed
- [x] Backup manifest written
- [x] Registry file-copy backup written
- [x] Copy hash verification passed
