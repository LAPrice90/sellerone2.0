# Execution Batch 005 - B025 SQL Primary Pilot

Date: 2026-04-28
Status: isolated verification passed

## Goal
- Prove the first B-owned runtime writer can use SQL as the primary write target while still producing the existing CSV compatibility export.

## Scope
- Pilot dataset: `B.TOKEN_COGS_LEDGER`
- Existing CSV export: `out/token_cogs_ledger.csv`
- SQL table: `b_token_cogs_ledger`

## Allowed Changes
- `scripts/flows/B/B025_build_token_cogs_ledger.py`
- `scripts/core/storage/*`
- `tests/test_b025_build_token_cogs_ledger.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL pilot mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- In SQL-primary mode, SQL write must complete before the CSV export is written.
- No Google Sheets changes are allowed in this batch.
- Do not restart schedulers or live loops during this batch.

## Implementation
- Add a shared dataframe-to-SQL replacement helper in `scripts/core/storage/`.
- Wire B025 to:
  - keep legacy CSV-only behavior in `csv` mode
  - write CSV then SQL in `sql_shadow` mode
  - write SQL then CSV in `sql_primary_csv_export` mode
- Add a focused test proving the SQLite pilot table and CSV export have the expected row.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_b025_build_token_cogs_ledger.py tests/test_storage_adapter.py`
- Required proof:
  - B025 tests pass in default CSV behavior.
  - B025 SQL-primary test writes `b_token_cogs_ledger` and exports `token_cogs_ledger.csv`.

## Runtime Proof
- Live loop proof is not run in this batch because the system remains paused and runtime mode remains default `csv`.
- Full B proof will require an approved B boundary run with `SELLERONE_STORAGE_MODE=sql_primary_csv_export` and `B_RUN_ONCE=1`.

## Result
- Code fix applied: yes - `scripts/core/storage/pandas_bridge.py` added and `scripts/flows/B/B025_build_token_cogs_ledger.py` now supports `csv`, `sql_shadow`, and `sql_primary_csv_export` modes.
- Isolated verification passed: yes - `python -m pytest tests/test_b025_build_token_cogs_ledger.py tests/test_storage_adapter.py` passed 10 tests; broader migration regression command passed 23 tests.
- Live loop verification: confirmed for B025 storage write - supervised `B_RUN_ONCE=1` run `B_20260428T125631Z` finalized with `B_EXIT rc=0`; `B025_build_token_cogs_ledger.py` completed with rc `0`; SQL table `b_token_cogs_ledger` row count `11817` matched CSV export `out/token_cogs_ledger.csv` row count `11817`.
- B-scoped health note: the proof run still reported existing B health `FAIL=1` and `WARN=3` (`token_shortages_by_sku`, `b_cycle_recent_fail_lines`, `b_listing_offer_collection`, `order_master_placeholder_cogs_rows`). These are not caused by the B025 SQL write, but they mean the whole B flow is not green.
