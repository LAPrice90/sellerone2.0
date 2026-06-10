# Execution Batch 037 - O/F Contract IO SQL Expansion

Started: 2026-04-29T15:12:00Z

## Why This Batch Exists
- Batch 036 moved the New Product Review pack to SQL, but the wider O/F contract layer still had many declared CSV files.
- Those contract files were real process handoffs, not random exports, so they needed a shared SQL-backed contract IO path instead of one-off patches.

## Scope
- Add SQL-aware O/F contract helpers:
  - `scripts/flows/O/_contract_io.py`
  - `scripts/flows/F/_contract_io.py`
- Move O contract writers and UI readers to SQL-first with CSV compatibility exports.
- Move F contract writer helpers to SQL-primary compatibility writes.
- Teach P006 to register O/F schema-declared contract paths so dependency counts are honest.
- Seed existing O/F contract CSVs into `out/sql/sellerone_dev.sqlite3`.

## Out Of Scope
- Do not remove compatibility CSV exports.
- Do not change Google Sheets.
- Do not pause or run B/H owners for this O/F-only batch.
- Do not fix unrelated F071 business-rule test failures around `missing_fee_cost_inputs`.

## Files Changed
- `scripts/flows/O/_contract_io.py`
- `scripts/flows/F/_contract_io.py`
- O flow files from O001/O002/O003/O005/O006/O010/O020/O030/O100/O200/O210/O300/O310/O400/O410/O420
- F flow files from F005/F010/F020/F030/F040/F050/F060/F061/F062/F070/F071/F072/F073/F074/F075
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `tests/test_flow_contract_io_sql.py`
- `tests/test_p006_build_csv_dependency_map.py`

## Backup And Pause
- O400 was paused before the live seed:
  - old O400 PID: `3064`
- SQLite backup before seed:
  - `out/backups/sql_storage_migration_v1/batch_037_o_f_contract_io_20260429T152410Z/sellerone_dev.sqlite3.before_contract_seed`
- B/H were left running because this batch did not write B/H-owned artifacts:
  - active B PID at precheck: `17208`
  - active H guarded PID at precheck: `30112`
  - active H cycle PID at precheck: `27228`

## Seed Evidence
- Seed command mode:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
- Seed summary:
  - artifact: `out/sql_migration/batch_037_o_f_contract_seed_summary.json`
  - status: `success`
  - seeded contracts: `59`
  - skipped missing declared contracts: `6`
  - total seeded rows: `1,824,415`
- Sample SQL row counts:
  - `o_restock_source_view`: `608`
  - `o_restock_recommendations_live`: `10`
  - `o_restock_review_queue`: `10`
  - `o_product_db_operator_view`: `608`
  - `f_supplier_price_list_universal_live`: `42,663`
  - `f_feeder_candidate_intake_live`: `2`
  - `f_feeder_shared_pass_logic_live`: `42,663`
  - `f_feeder_approval_queue_live`: `9,552`

## O400 Restart And SQL Load Proof
- O400 restarted from SQL-default launcher:
  - new O400 PID: `2592`
  - port: `8501`
- SQL-mode O400 loader proof:
  - `restock_source_view`: `608`
  - `restock_review_queue`: `10`
  - `restock_recommendations_live`: `10`
  - `product_db_operator_view`: `608`
  - `restock_decision_events`: `22`
  - `restock_decisions_log`: `6`
  - `purchase_orders_live`: `1`
  - `purchase_order_lines_live`: `1`
  - `ordered_stock_state`: `1`
  - `receiving_events`: `3`
  - `receiving_event_holds`: `2`
  - New Product Review pass rows: `3`
  - New Product Review near-miss rows: `1600`
  - feeder review events: `13`

## Dependency Map
- Refreshed artifact:
  - `out/sql_migration/csv_dependency_map_summary.json`
- Latest counts:
  - `row_count=1858`
  - `registered_dependency_count=503`
  - `sql_primary_pilot_proven_count=526`
  - `csv_dependency_remaining_count=6`
  - `unresolved_dynamic_count=715`
  - `unregistered_csv_count=640`
- Remaining registered CSV dependencies:
  - `F.SUPPLIER_DISCOVERY_HANDOFF`
  - `O.RESTOCK_REVIEW_LOG`
  - `O.SUPPLIER_PROFILES`
  - `O.SUPPLIER_LEAD_TIME_HISTORY`

## Tests
- Passed:
  - `pytest ...O/F/P006 selected suite...`
  - result: `178 passed`
- Passed O-specific follow-up:
  - result: `80 passed`
- Broad F071 note:
  - `tests/test_f071_build_backtest_input_view.py` still has 6 business-rule failures around `missing_fee_cost_inputs`.
  - These are not caused by SQL contract IO and were not masked.

## Status
- code fix applied: yes.
- isolated verification passed: yes.
- live seed proof passed: yes for O/F contract SQL tables seeded from current CSV compatibility files.
- live O400 restoration confirmed: yes, O400 is listening on port `8501` with PID `2592`.
- next move: continue with remaining unregistered CSV groups, starting with B/D finance files when a B-safe maintenance window is available.
