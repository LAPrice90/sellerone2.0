# Execution Batch 006 - B010 Token Ops SQL Expansion

Date: 2026-04-28
Status: isolated verification passed

## Goal
- Extend the B SQL-primary pattern from the B025 pilot to the next token operations outputs.

## Scope
- Datasets:
  - `B.ORDER_COGS_FROM_TOKENS`
  - token movement output used by the token operations sheet/export path
- Existing CSV exports:
  - `out/token_movement_log.csv`
  - `out/order_cogs_from_tokens.csv`
- SQL tables:
  - `b_token_movement_log`
  - `b_order_cogs_from_tokens`

## Allowed Changes
- `scripts/flows/B/B010_build_token_ops_outputs.py`
- `scripts/core/storage/*`
- `tests/test_b010_build_token_ops_outputs.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL expansion mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- In SQL-primary mode, both SQL tables are replaced in one transaction before either CSV export is written.
- Existing Sheets behavior remains controlled by the existing token ops env flags. No Sheets writes are enabled by this batch.
- Do not restart schedulers or live loops during this batch.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_b010_build_token_ops_outputs.py tests/test_b025_build_token_cogs_ledger.py tests/test_storage_adapter.py`
- Required proof:
  - B010 SQL-primary test writes both SQL tables and both CSV exports.
  - Existing B025 pilot tests still pass.

## Runtime Proof
- Live loop proof is not run in this batch because the system remains paused and default runtime mode remains `csv`.
- Full B proof still requires an approved boundary run with `SELLERONE_STORAGE_MODE=sql_primary_csv_export` and `B_RUN_ONCE=1`.

## Result
- Code fix applied: yes - `scripts/flows/B/B010_build_token_ops_outputs.py` now supports SQL-primary writes for `b_token_movement_log` and `b_order_cogs_from_tokens`, then exports the existing CSV files.
- Isolated verification passed: yes - `python -m pytest tests/test_b010_build_token_ops_outputs.py tests/test_b025_build_token_cogs_ledger.py tests/test_storage_adapter.py` passed 11 tests; broader migration regression command passed 24 tests.
- Runtime verification: confirmed by isolated local B-script proof - `B010_build_token_ops_outputs.py` ran with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, Sheets writes disabled, and wrote SQL tables before CSV exports. SQL row counts matched CSV export row counts: `b_token_movement_log` `92620`, `out/token_movement_log.csv` `92620`; `b_order_cogs_from_tokens` `10180`, `out/order_cogs_from_tokens.csv` `10180`.
- Live loop verification: not applicable to the current B cycle path because B010 is not in `scripts/cycles/run_B_cycle.py`; it is run by the daily finance/token operations path.
