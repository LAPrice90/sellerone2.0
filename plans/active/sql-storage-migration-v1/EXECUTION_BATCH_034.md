# Execution Batch 034 - A-Owned SQL-Primary Isolated Proof

Started: 2026-04-28T16:23:00Z

## Goal
- Run an A-owned proof path under `sql_primary_csv_export`.
- Keep scheduled tasks disabled.
- Keep Google Sheets writes disabled.
- Avoid token mutation steps during this storage proof.

## Scope
- `scripts/cycles/run_A_all.py`
- A local output CSV compatibility exports.
- A manifests, A scoped health outputs, rollback proof artifacts.
- `plans/active/sql-storage-migration-v1/*`

## Preflight Evidence
- P002 forced proof output: `plans/active/sql-storage-migration-v1/forced_proof_A.json`
- A proof window status: `ready_now`.
- No active B cycle lock.
- No active maintenance markers after stale markers from the stopped accidental preflight were cleared.
- Scheduled tasks remain disabled.

## Safety Controls
- Use the owned A runner, not standalone A015.
- Set `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- Set `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`.
- Set `A_SKIP_LEGACY_SHEET_OUTPUT_STEPS=1`.
- Set `A_ENABLE_STOCK_RECEIPTS_SHEET=0`.
- Set `INVENTORY_WRITE_SHEETS=0`.
- Set `ORDER_MASTER_WRITE_SHEETS=0`.
- Set `FIN_L3_SKIP_SHEETS=1`.
- Set `E_WRITE_SHEETS=0`.
- Set `A_ENSURE_B_AFTER_A=0`.
- Set `A_EXTRA_SKIP_STEPS=A010_apply_researching_delta.py,A020_run_daily_finance.py` to avoid token mutation during the isolated storage proof.
- Set `A_B_RECOVERY_USE_SCHEDULER=0` to keep scheduler ownership paused after A proof.

## Stop Conditions
- Any Google Sheets write attempt.
- Any token ledger row-count movement outside a planned token mutation proof.
- Any A cycle failure.
- Any A scoped health `FAIL`.
- Any SQL/CSV rollback export mismatch.

## Status
- code fix applied: yes - added `A_EXTRA_SKIP_STEPS` and disabled B recovery support to `scripts/cycles/run_A_all.py` for bounded isolated proof windows. Updated `scripts/run_A_all.py` so tests that import the wrapper see the real runner module.
- isolated verification passed: yes.
- live loop verification: not yet proven. Scheduler ownership remains paused by design.

## Proof Evidence
- Compile check passed for `scripts/run_A_all.py`, `scripts/cycles/run_A_all.py`, and `scripts/cycles/run_H_pricing_cycle.py`.
- Focused A/storage tests passed: `26 passed`.
- Final A isolated proof run id: `20260428T163536Z`.
- Final A manifest: `out\manifests\A\2026-04-28\20260428T163536Z.json`.
- Final A manifest state: `completed`.
- Final A manifest step counts: `recorded=13`, `configured=13`, `launched=4`, `completed=4`.
- Final A scoped health: `0 FAIL`, `0 WARN`, `6 OK`.
- Rollback validation: `48 pass`, `0 fail`, report `out\sql_migration\rollback_exports_20260428T163913Z\rollback_export_report.csv`.
- Dependency map refresh: `csv_dependency_remaining_count=0`, `registered_dependency_count=156`, `sql_primary_pilot_proven_count=164`, `unresolved_dynamic_count=800`, `unregistered_csv_count=285`.
- Token ledger stability after final proof:
  - `out\token_ledger_live.csv`: `13594` rows, sha256 `b2b7da263a1a90407bef0a8a11bec0c9733a293dd974267a9f9f3f30bf9d6a93`
  - `out\systems\B\live\token_ledger_live.csv`: `13594` rows, same sha256
  - `out\token_allocations_live.csv`: `11813` rows, sha256 `e7b53a070a0a94bffd23687e65861c1a4ad3a0b7a11aaf2c712fea9133d7cccc`
  - `out\systems\B\live\token_allocations_live.csv`: `11813` rows, same sha256
- Ownership after final proof: no Python process, no A lock, no B lock, no maintenance markers.
- `AMZ Orders` remained disabled.

## Side Effect Reconciled
- First A proof attempt ran A010 and changed `out\systems\B\live\token_ledger_live.csv`.
- The changed file was backed up to `out\sql_migration\batch034_token_ledger_restore\`.
- `out\systems\B\live\token_ledger_live.csv` was restored to match `out\token_ledger_live.csv` before the final proof.
- Final proof skipped A010 and A020, and token hashes remained stable.
