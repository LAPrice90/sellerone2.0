# Execution Batch 002

## Purpose
- Add the SQL storage adapter skeleton and migration framework without changing runtime flow behavior.

## Scope Guardrails
- Only add shared storage infrastructure and tests.
- Do not change A, B, E, H, O, or Feeder business scripts in this batch.
- Do not seed SQL from live data in this batch.
- Do not change Google Sheets.
- Do not restart paused schedulers until the user approves the next operating state.

## Files Allowed To Change
- `scripts/core/storage/*`
- `tests/test_storage_*`
- `plans/active/sql-storage-migration-v1/*`

## Inputs To Read First
- `plans/active/sql-storage-migration-v1/PLAN.md`
- `plans/active/sql-storage-migration-v1/CODING_PLAN.md`
- `project_control/ARCHITECTURE.md`
- `scripts/core/out_paths.py`
- `tests/test_phase1_storage.py`

## Tasks
### Task 1 - Storage Config
- Goal: add storage-mode parsing and DB target configuration.
- Files: `scripts/core/storage/config.py`
- Notes: support `csv`, `sql_shadow`, and `sql_primary_csv_export`.

### Task 2 - DB Adapter
- Goal: add a small DB-API adapter with transaction and query helpers.
- Files: `scripts/core/storage/adapter.py`
- Notes: use SQLite for tests/local development. PostgreSQL is the production target but driver import is optional until install/config is approved.

### Task 3 - Migration Metadata
- Goal: add a minimal schema migration ledger.
- Files: `scripts/core/storage/adapter.py`
- Notes: create `schema_migrations` and record applied migration IDs.

### Task 4 - Tests
- Goal: prove config parsing, SQLite transactions, rollback behavior, and idempotent migration behavior.
- Files: `tests/test_storage_adapter.py`

## Tests
- Command: `python -m pytest tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py`
- Expected result: all tests pass.

## Monitoring Plan
- Live proof needed: no.
- Forced proof window: not needed for code skeleton.
- Artifacts to poll: none.
- Poll cadence: none.
- Success threshold: tests pass.
- Timeout rule: not applicable.
- Fallback if forced proof is blocked: not applicable.
- Next phase after success: Batch 003 CSV-to-SQL seed/export utilities.
- Notification mode: final or phase-complete only.
- User interruption threshold: storage target decision or dependency install approval needed.

## Proof Required
- Tests pass.
- No runtime flow scripts changed.
- No SQL seed or cutover attempted.

## Completion Checklist
- [x] Scope held
- [x] Files changed only in allowed set
- [x] Tests passed
- [x] Plan status updated

## Proof Notes
- Added storage config and adapter package under `scripts/core/storage/`.
- Added `tests/test_storage_adapter.py`.
- Test command: `python -m pytest tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py`
- Result: 13 passed.
- No runtime flow script was changed.
- No SQL seed or cutover was attempted in this batch.
