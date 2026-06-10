# Execution Batch 030 - Rollback Export Validation And Re-Enable Plan

Date: 2026-04-28
Status: guarded local rollback validation passed

## Goal
- Prove SQL can export rollback-compatible CSVs without overwriting live artifacts.
- Record the controlled proof sequence required before paused scheduler ownership is restored.

## Scope
- New rollback validation tool:
  - `scripts/one_off/P007_validate_sql_rollback_exports.py`
- Tests:
  - `tests/test_p007_validate_sql_rollback_exports.py`
- Plan:
  - `plans/active/sql-storage-migration-v1/REENABLE_PROOF_PLAN.md`

## Safety Rules
- Do not write rollback exports into live `out/` paths.
- Do not re-enable scheduled tasks in this batch.
- Do not run live A015, API collectors, Sheet writers, or token mutation scripts.

## Verification
- Rollback export validation:
  - `python scripts/one_off/P007_validate_sql_rollback_exports.py --sqlite-path out/sql/sellerone_dev.sqlite3 --output-dir out/sql_migration --format text`
- Result:
  - `status=passed`
  - `checked_count=48`
  - `pass_count=48`
  - `fail_count=0`
  - `missing_csv_count=0`
  - `missing_table_count=0`
  - export dir: `out/sql_migration/rollback_exports_20260428T144628Z`
- Focused tests:
  - `PYTHONPATH=<repo_root> pytest tests/test_p007_validate_sql_rollback_exports.py tests/test_storage_adapter.py`
  - result: `11 passed`

## Current Result
- Code fix applied: yes - rollback exports now validate row counts, headers, and canonical CSV hashes against live compatibility CSVs.
- Isolated verification passed: yes - focused rollback/storage tests passed.
- Guarded rollback validation passed: yes - all `48` mapped SQL tables exported and matched current compatibility CSVs.
- Scheduler restoration not executed: re-enable proof sequence is documented but not run.
