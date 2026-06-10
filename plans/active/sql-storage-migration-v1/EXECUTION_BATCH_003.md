# Execution Batch 003

## Purpose
- Add CSV-to-SQL shadow seed and SQL-to-CSV export utilities for backed-up registry datasets.

## Scope Guardrails
- Only seed from the frozen backup bundle, not from live paths.
- SQL shadow tables are read-only proof copies for this batch.
- Do not switch runtime reads or writes to SQL.
- Do not change Google Sheets.
- Do not restart paused schedulers until the user approves the next operating state.

## Files Allowed To Change
- `scripts/one_off/P004_seed_sql_shadow_from_manifest.py`
- `tests/test_p004_seed_sql_shadow_from_manifest.py`
- `plans/active/sql-storage-migration-v1/*`

## Tasks
### Task 1 - Shadow Seed
- Goal: read `manifest.csv` and load backed-up CSV/TSV files into SQLite shadow tables.
- Notes: table names are derived from `dataset_id`; all source fields are stored as text.

### Task 2 - Export
- Goal: export one seeded dataset back to CSV for reconciliation.
- Notes: export should preserve original header order where possible.

### Task 3 - Proof Metadata
- Goal: record seeded table names, source paths, row counts, and source headers.

## Tests
- Command: `python -m pytest tests/test_p004_seed_sql_shadow_from_manifest.py tests/test_storage_adapter.py`
- Expected result: all tests pass.

## Proof Required
- Fixture seed/export round trip passes.
- Registry backup seed completes against the frozen backup bundle.
- Seed summary records table count and total row count.

## Completion Checklist
- [x] Scope held
- [x] Files changed only in allowed set
- [x] Tests passed
- [x] Frozen registry backup seeded
- [x] Plan status updated

## Proof Notes
- Added `scripts/one_off/P004_seed_sql_shadow_from_manifest.py`.
- Added `tests/test_p004_seed_sql_shadow_from_manifest.py`.
- Test command: `python -m pytest tests/test_p004_seed_sql_shadow_from_manifest.py tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py`
- Result: 17 passed.
- Frozen backup seeded:
- SQLite path: `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/shadow.sqlite3`
- table_count: `45`
- row_count: `424784`
- Export proof:
- dataset: `B.ORDERS_ALL`
- manifest row count: `10450`
- exported row count: `10450`
- match: `true`
- Summary artifact: `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/shadow_seed_summary.json`
- No runtime flow script was changed.
- No SQL cutover was attempted.
