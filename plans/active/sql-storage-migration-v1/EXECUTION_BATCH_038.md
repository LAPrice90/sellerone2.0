# Execution Batch 038 - B Finance And Order SQL Expansion

## Scope
- Added shared B finance SQL IO in `scripts/flows/B/_finance_io.py`.
- Converted B finance/order reads or writes in:
  - `B001_run_orders_to_sheet.py`
  - `B002_run_pending_orders_to_sheet.py`
  - `B003_run_financial_events_level3.py`
  - `B004_build_order_master.py`
  - `B007_allocate_tokens_live.py`
  - `B024_build_tokens_november_anchor.py`
  - `B032_update_token_lot_rank_from_orders_sheet.py`
- Registered the B finance/order CSV group in `project_control/DATA_BLUEPRINT_REGISTRY.csv`.
- Marked those registered dataset IDs as SQL-primary pilot proven in `P006_build_csv_dependency_map.py`.

## Maintenance Boundary
- B maintenance requested: `2026-04-29T16:39:40Z`.
- B `maintenance.ready`: `2026-04-29T16:41:00Z`.
- Maintenance active marker set while code, seed, tests, and local proof ran.
- Maintenance cleared for live proof after seed and tests.
- Post-proof state: `maintenance.ready=0`, `maintenance.requested=0`, `maintenance.active=0`.

## Backup
- SQLite backup:
  - `out/backups/sql_storage_migration_v1/batch_038_b_finance_20260429T165015Z/sellerone_dev.sqlite3.before_b_finance_seed`

## SQL Seed
- Seed summary:
  - `out/sql_migration/batch_038_b_finance_seed_summary.json`
- Non-empty seeded tables matched SQL row counts.
- Key seeded counts:
  - `b_orders_raw`: 898 at seed time
  - `b_orders_all`: 10520
  - `b_order_items_all`: 10542
  - `b_financial_events_level1`: 10255
  - `b_financial_events_level2`: 10215
  - `b_financial_events_level3_raw`: 177886
  - `b_financial_events_level3_raw_dedup`: 162572
  - `b_financial_events_level3_summary`: 134315
  - `b_financial_events_level3_official`: 10220
  - `b_financial_events_account_ledger`: 1343
  - `b_financial_events_refunds`: 1789
  - `b_financial_events_refunds_official`: 191
  - `b_orders_sheet_orders`: 1653
  - `b_order_master`: 10250
- `out/order_items_raw.csv` was a zero-byte empty snapshot, so no header/table could be seeded for that one path. B001 will create the SQL table when that snapshot has rows/header again.

## Tests
- Compile check passed:
  - `python -m py_compile scripts/flows/B/_finance_io.py scripts/flows/B/B001_run_orders_to_sheet.py scripts/flows/B/B002_run_pending_orders_to_sheet.py scripts/flows/B/B003_run_financial_events_level3.py scripts/flows/B/B004_build_order_master.py scripts/flows/B/B007_allocate_tokens_live.py scripts/flows/B/B024_build_tokens_november_anchor.py scripts/flows/B/B032_update_token_lot_rank_from_orders_sheet.py scripts/one_off/P006_build_csv_dependency_map.py`
- Targeted tests passed:
  - `python -m pytest tests/test_b_finance_io_sql.py tests/test_b003_run_financial_events_level3.py tests/test_b004_level_gate.py tests/test_b007_allocate_tokens_live.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b_token_live_storage.py tests/test_p006_build_csv_dependency_map.py -q`
  - Result: `29 passed`

## Local Proof
- Ran `B004_build_order_master.py` under:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
  - `B_CYCLE_QUIET=1`
  - `ORDER_MASTER_SKIP_SHEETS=1`
- Result:
  - status `success`
  - rows `10250`
  - output `out/order_master.csv`
  - Sheet writes disabled

## Dependency Map
- Refreshed with `P006_build_csv_dependency_map.py`.
- Summary:
  - `row_count=1824`
  - `registered_dependency_count=508`
  - `sql_primary_pilot_proven_count=537`
  - `csv_dependency_remaining_count=0`
  - `unresolved_dynamic_count=710`
  - `unregistered_csv_count=606`

## Live B Proof
- Paused cycle finalized after maintenance clear:
  - `B_20260429T163556Z`
  - finalized at `2026-04-29T16:55:55Z`
- Updated live B cycle proof:
  - manifest `out/manifests/B/2026-04-29/B_20260429T165555Z.json`
  - start `2026-04-29T16:55:55Z`
  - end `2026-04-29T17:07:20Z`
  - final state `completed`
  - recorded steps `12`
  - completed steps `12`
- Storage-sensitive steps completed with `rc=0`:
  - `B001_run_orders_to_sheet.py`
  - `B002_run_pending_orders_to_sheet.py`
  - `B007_allocate_tokens_live.py`
  - `B025_build_token_cogs_ledger.py`
  - `B004_build_order_master.py`
  - `B006_build_fx_ledgers.py`
  - `B011_recover_l3_orphans.py`

## Residual Health State
- `out/cycle_alerts/checklist_B_split.csv` still reports:
  - FAIL: `token_shortages_by_sku`
  - WARN: `order_master_placeholder_cogs_rows`
- These were known B data/stock issues before Batch 038 and are not storage migration proof failures.

## Next Move
- Continue with remaining unregistered CSV groups: token reconciliation, transaction/PnL ledgers, merchant listing snapshots, inbound status/cost, fee VAT/reporting outputs, and config/reference CSVs.
