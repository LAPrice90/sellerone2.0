# Execution Batch 004

## Purpose
- Reconcile the SQL shadow database against the frozen registry backup manifest before any runtime cutover.

## Scope Guardrails
- Read only from the frozen backup manifest and shadow SQLite DB.
- Do not read live runtime CSVs for reconciliation.
- Do not change runtime flow scripts.
- Do not change Google Sheets.
- Do not restart paused schedulers until the user approves the next operating state.

## Files Allowed To Change
- `scripts/one_off/P005_reconcile_sql_shadow.py`
- `tests/test_p005_reconcile_sql_shadow.py`
- `plans/active/sql-storage-migration-v1/*`

## Tasks
### Task 1 - Reconciliation Report
- Goal: compare each seedable manifest dataset against SQL shadow metadata and actual table counts.
- Notes: duplicate mirror rows, empty source files, missing registry targets, and non-tabular rows must be classified explicitly.

### Task 2 - Summary Artifact
- Goal: write row-level report and summary JSON into the backup bundle.

### Task 3 - Proof
- Goal: prove all seeded tables reconcile before planning any runtime SQL pilot.

## Tests
- Command: `python -m pytest tests/test_p005_reconcile_sql_shadow.py tests/test_p004_seed_sql_shadow_from_manifest.py tests/test_storage_adapter.py`
- Expected result: all tests pass.

## Proof Required
- Reconciliation summary has `fail_count=0`.
- Seeded table count matches the Batch 003 seed table count.
- Missing, duplicate, empty, and non-tabular items are classified rather than hidden.

## Completion Checklist
- [x] Scope held
- [x] Files changed only in allowed set
- [x] Tests passed
- [x] Frozen shadow reconciliation passed
- [x] Plan status updated

## Proof Notes
- Added `scripts/one_off/P005_reconcile_sql_shadow.py`.
- Added `tests/test_p005_reconcile_sql_shadow.py`.
- Test command: `python -m pytest tests/test_p005_reconcile_sql_shadow.py tests/test_p004_seed_sql_shadow_from_manifest.py tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py`
- Result: 20 passed.
- Reconciliation command: `python scripts/one_off/P005_reconcile_sql_shadow.py --manifest out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/manifest.csv --sqlite-path out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/shadow.sqlite3 --output-dir out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/reconciliation --format text`
- Reconciliation result:
- status: `passed`
- pass_count: `45`
- fail_count: `0`
- duplicate_skipped_count: `3`
- empty_skipped_count: `1`
- missing_source_count: `7`
- non_tabular_count: `2`
- seeded_table_count: `45`
- Report: `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/reconciliation/shadow_reconciliation_report.csv`
- Summary: `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/reconciliation/shadow_reconciliation_summary.json`
- No runtime flow script was changed.
- No SQL cutover was attempted.
