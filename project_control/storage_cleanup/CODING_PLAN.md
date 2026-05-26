# Emergency Storage Cleanup - 2026-05-25

## Current Phase
- Status: executing emergency cleanup.
- Goal: recover disk space, stop repeated full SQLite backup creation, and preserve one rollback path.
- Scope: local files only. No Google Sheets changes. No local DB alignment changes.

## Approved Cleanup Policy
- F loop handling: pause scheduled ownership before deleting storage.
- F storage-drift backups: keep newest non-empty folder only.
- H staged snapshots: keep newest 5 folders only.
- Old Desktop/archive copies: delete approved old copies and raw reference archive.
- Current live SQL database must remain: `out/sql/sellerone_dev.sqlite3`.

## Allowed Files And Targets
- Code edits:
  - `scripts/flows/F/price_list_manager/FPM129_storage_drift_guard.py`
  - `scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py` only if needed for compatibility.
  - `tests/test_fpm129_storage_drift_guard.py`
  - `tests/test_fpm130_live_cycle.py` only if needed for compatibility.
  - `project_control/FEEDER_V1_PRICE_LIST_PROCESS_MANAGER_GUIDEBOOK.md`
  - `project_control/EXPECTATIONS/feeder_cycle_expectations.md`
- Cleanup targets:
  - `out/backups/f_storage_drift_reconcile_*`, except newest kept non-empty backup.
  - `out/systems/H/staged/*`, except newest 5 staged folders.
  - `C:/Users/Luke/Desktop/SellerOne 2.0 - Copy (2)`
  - `C:/Users/Luke/Desktop/AMZ Manager 1`
  - `C:/Users/Luke/Desktop/AMZ Manager 1 - Copy`
  - `reference/Reference only`
- Operational controls:
  - Windows scheduled task `AMZ Price List Manager`
  - `out/locks/maintenance.requested`

## Proof Checklist
- Before deletion, write manifest with exact paths, sizes, and keep/delete decision.
- Confirm F ownership is paused and no FPM/F061 Python owner process is running.
- Confirm no new `f_storage_drift_reconcile_*` folders appear for 2 minutes.
- After cleanup, prove:
  - `C:` free space is greater than 500 GB.
  - Exactly 1 non-empty F storage-drift backup folder remains.
  - 0 empty F storage-drift backup folders remain.
  - Exactly 5 H staged folders remain.
  - `out/sql/sellerone_dev.sqlite3` exists.
- Run:
  - `python -m py_compile scripts/flows/F/price_list_manager/FPM129_storage_drift_guard.py scripts/flows/F/price_list_manager/FPM130_run_live_cycle.py`
  - `python -m pytest tests/test_fpm129_storage_drift_guard.py tests/test_fpm130_live_cycle.py -q`

## Monitoring
- Resume `AMZ Price List Manager` only after cleanup and code proof pass.
- Watch `out/backups/f_storage_drift_reconcile_*` at +5 minutes, +10 minutes, then every +15 minutes up to +60 minutes.
- Success: no new non-empty F storage-drift backup folders appear unless an actual reconcile write happened.
- Failure path: disable `AMZ Price List Manager`, inspect `out/systems/F/price_list_manager/live/storage_drift_report.csv`, and keep F paused until backup behavior is corrected.

## Execution Evidence
- Cleanup manifest: `project_control/storage_cleanup/cleanup_manifest.20260525T081309Z.csv`.
- Estimated cleanup from manifest: `667.123 GB`.
- F storage-drift cleanup: removed `4067` folders, kept `f_storage_drift_reconcile_20260524T085426Z`.
- H staged cleanup: removed `236` folders, kept newest `5`.
- Approved old archive cleanup: removed `4` folders.
- Git cleanup: `git gc --prune=now` reduced `.git` loose objects from `35.62 GiB` to `0 bytes`; final pack size `53.06 MiB`.
- Post-cleanup proof:
  - `C:` free bytes: `758925795328`.
  - F storage-drift folders: `1`.
  - F non-empty storage-drift folders: `1`.
  - F empty storage-drift folders: `0`.
  - H staged folders: `5`.
  - `out/sql/sellerone_dev.sqlite3` exists: `True`.
- Code proof:
  - `python -m py_compile scripts\flows\F\price_list_manager\FPM129_storage_drift_guard.py scripts\flows\F\price_list_manager\FPM130_run_live_cycle.py` passed.
  - `python -m pytest tests\test_fpm129_storage_drift_guard.py tests\test_fpm130_live_cycle.py -q` passed: `75 passed`.
- Resume proof:
  - `out/locks/maintenance.requested` cleared.
  - `AMZ Price List Manager` accepted `Start-ScheduledTask`; last run result `0`.
  - F manager resumed under PID `32120`.
- Monitoring proof:
  - Output: `project_control/storage_cleanup/monitoring.20260525T083018Z.csv`.
  - Checkpoints passed at `+5m`, `+10m`, `+25m`, `+40m`, `+55m`, and `+60m`.
  - Result: no backup recurrence, F manager PID alive, F storage-drift backup count stayed at `1`, empty backup folders stayed at `0`.
