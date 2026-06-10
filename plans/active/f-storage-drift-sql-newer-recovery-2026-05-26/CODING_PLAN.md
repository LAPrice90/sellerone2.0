# F Storage Drift SQL-Newer Recovery - 2026-05-26

## Current Phase
Scoped Codex-owned recovery for `feeder_legacy_chart_daily_raw_live`.

## Manager Task
- `F_storage_drift_preflight_4ddda80247`
- Status at start of this batch: `in_progress`

## Allowed Files
- `scripts/one_off/F042_recover_sql_newer_storage_drift.py`
- `tests/test_f042_recover_sql_newer_storage_drift.py`
- `tests/test_fpm129_storage_drift_guard.py`
- `tests/test_sellerone_manager_control_plane.py`
- `sellerone_manager/`
- `out/systems/F/price_list_manager/recovery/`
- `out/systems/F/live/feeder_legacy_chart_daily_raw_live.csv`
- `out/backups/f_sql_newer_csv_recovery_*`
- `out/systems/M/`

## Not Allowed
- No Google Sheets writes.
- No local DB-wide alignment.
- No F061 queue edits.
- No supplier queue deletion.
- No broad A/B/E/H worker runs.
- No worker restart in this batch.

## Live Evidence Before Apply
- Contract: `feeder_legacy_chart_daily_raw_live`
- CSV rows: `7437`
- SQL rows: `34450`
- SQL-only exact rows: `27013`
- CSV-only exact rows: `0`
- CSV freshness: `2026-05-21T12:25:39Z`
- SQL freshness: `2026-05-25T11:42:47Z`
- Dry-run status: `ready_sql_newer_recovery`
- Dry-run report: `out/systems/F/price_list_manager/recovery/sql_newer_recovery_summary.csv`

## Proof Plan
- Compile changed files.
- Run focused tests:
  - `tests/test_fpm129_storage_drift_guard.py`
  - `tests/test_f042_recover_sql_newer_storage_drift.py`
  - `tests/test_sellerone_manager_control_plane.py`
- Apply SQL-to-CSV recovery only for `feeder_legacy_chart_daily_raw_live`.
- Run storage drift dry check across critical F contracts.
- Run the read-only manager.
- Confirm the manager queue does not duplicate the task.

## Success Threshold
- Rebuilt CSV row count equals SQL row count for `feeder_legacy_chart_daily_raw_live`.
- Storage drift report has `blocked_rows=0`.
- Manager execution errors are `0`.
- Manager no longer reports CLF as directly blocked by active storage drift.
- Recovery backup exists.

## Proof Update - 2026-05-26T11:50Z
- Manager task `F_storage_drift_preflight_4ddda80247` moved:
  - `queued` to `in_progress`
  - `in_progress` to `cleared_pending_review`
  - `cleared_pending_review` to `completed`
- Added isolated one-off recovery tool:
  - `scripts/one_off/F042_recover_sql_newer_storage_drift.py`
- Added focused recovery tests:
  - `tests/test_f042_recover_sql_newer_storage_drift.py`
- Extended storage guard and manager tests for SQL-newer blocking and stale live-owner status handling.
- Compile passed.
- Focused tests passed:
  - `python -m pytest tests/test_fpm129_storage_drift_guard.py tests/test_f042_recover_sql_newer_storage_drift.py tests/test_sellerone_manager_control_plane.py -q`
  - result: `21 passed`
- Live dry-run evidence before apply:
  - contract: `feeder_legacy_chart_daily_raw_live`
  - CSV rows: `7437`
  - SQL rows: `34450`
  - shared exact rows: `7437`
  - SQL-only exact rows: `27013`
  - CSV-only exact rows: `0`
  - status: `ready_sql_newer_recovery`
- Apply result:
  - status: `applied_sql_to_csv_recovery`
  - rebuilt CSV rows: `34450`
  - rollback backup: `out/backups/f_sql_newer_csv_recovery_20260526T114817Z`
- Storage drift proof after apply:
  - `status=ok`
  - `checked_contracts=7`
  - `drift_rows=0`
  - `blocked_rows=0`
- Manager proof after apply:
  - `status=ok`
  - `manager_execution_errors=0`
  - `header_errors=0`
  - report says no active F manager blocker
  - report says no direct user task and no active Codex repair task
- No Google Sheets writes, F061 queue edits, supplier queue deletion, broad A/B/E/H runs, or worker restarts were performed by Codex.
