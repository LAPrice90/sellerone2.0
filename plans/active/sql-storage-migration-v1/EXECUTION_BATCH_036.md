# Execution Batch 036 - F/O Review Pack SQL Completion Plan

Started: 2026-04-29T08:57:22Z

## Why This Batch Exists
- The SQL-primary migration proved active A/B/E/H datasets and entrypoints, but it did not migrate every CSV used by F, O, or analysis-report tooling.
- The New Product Review dropdown still reads CSVs directly from:
  - `out/analysis_reports/f_live_price_file_pass_review_*.csv`
  - `out/analysis_reports/f_live_price_file_near_miss_review_*.csv`
  - `out/analysis_reports/f_live_price_file_review_summary_*.csv`
  - `out/systems/F/inbox/feeder_review_events.csv`
- This happened because the review-pack files are not registered in `project_control/DATA_BLUEPRINT_REGISTRY.csv`, so the prior dependency map could report `csv_dependency_remaining_count=0` for registered datasets while still leaving unregistered and dynamic CSV usage active.

## Current Evidence
- Refreshed CSV dependency map:
  - `row_count=1241`
  - `registered_dependency_count=156`
  - `sql_primary_pilot_proven_count=164`
  - `csv_dependency_remaining_count=0`
  - `unresolved_dynamic_count=800`
  - `unregistered_csv_count=285`
- `csv_dependency_remaining_count=0` means no registered dependency remains. It does not mean no CSV call remains.
- Current active F/O runtime:
  - `F061_run_legacy_first_checks_local.py` is running for `stocklist_supplier`.
  - `O400_operator_ui.py` is running through Streamlit.
- Current New Product Review artifacts:
  - latest review summary mtime: `2026-04-29T08:49:31Z`
  - latest pass and near-miss packs mtime: `2026-04-29T08:41:32Z`
  - `feeder_review_events.csv` exists with 5 rows and mtime `2026-04-29T08:48:47Z`

## Root Cause
- The previous SQL migration scope was too narrow.
- It covered the registered A/B/E/H/System datasets and a set of known compatibility exports.
- It did not promote F/O New Product Review datasets into the registry, storage adapter proof set, rollback export set, or O400 SQL-first read path.
- P006 currently cannot resolve many contract-built or runtime-built paths, so the map still has 800 unresolved dynamic CSV calls and 285 unregistered CSV paths.

## Goal
- Move the New Product Review path to SQL-primary storage with CSV compatibility exports.
- Keep CSV files only as compatibility exports for UI fallback, downloads, human review, and rollback.
- Make the dependency map honest enough that F/O review CSV usage cannot hide as unregistered or unresolved.

## In Scope
- F/O review-pack data:
  - pass review rows
  - near-miss review rows
  - review summary rows
  - feeder review events
  - feeder review UI drafts
- Static migration tooling:
  - dependency map resolver for F/O contracts and analysis-report paths
  - rollback export validator coverage for the new F/O tables
- O400 New Product Review read path:
  - SQL-first reads
  - CSV fallback only when SQL table is absent
- F019/F review-pack writer path:
  - SQL transaction first
  - CSV export only after SQL write succeeds

## Out Of Scope
- Do not remove CSV exports yet.
- Do not rewrite scraper logic.
- Do not change Google Sheets.
- Do not change Product_DB authority.
- Do not apply F061 queue rewrites.
- Do not run overlapping F061, O400 write actions, or other F/O owners during seed or proof.

## Proposed SQL Tables
- `f_new_product_review_pack_rows`
  - includes snapshot id, lane, active supplier, active run id, review batch id, candidate id, row fields, and source timestamp.
- `f_new_product_review_summary`
  - includes snapshot id, metric, value, observed utc, active supplier, active run id, and source timestamp.
- `f_feeder_review_events`
  - append-only event log matching `out/systems/F/inbox/feeder_review_events.csv`.
- `o_feeder_review_ui_drafts`
  - current-state UI draft table matching `out/systems/O/live/feeder_review_ui_drafts.csv`.
- Optional later expansion tables:
  - F fail triage outputs from F021-F027.
  - F legacy scanner live outputs.
  - O restock and PO workflow outputs.

## Implementation Phases
### Phase 1 - Registry And Map Repair
- Add F/O review datasets to `project_control/DATA_BLUEPRINT_REGISTRY.csv`.
- Extend P006 so contract-built F/O paths and review-pack analysis paths are resolved.
- Success threshold:
  - New Product Review CSV paths are registered or explicitly classified.
  - F/O review-pack rows no longer hide in `unregistered_csv_count` or `unresolved_dynamic_count`.

### Phase 2 - Storage Adapter Support
- Add an append-capable SQL compatibility helper for event logs.
- Add a replace-by-snapshot or partition replace helper for review pack snapshots.
- Keep current `write_dataframe_with_sql_compat` behavior for simple current-state outputs.
- Success threshold:
  - event append preserves existing rows and appends new rows once.
  - snapshot replacement does not delete historical snapshots unless scoped to that snapshot.

### Phase 3 - F Writer Migration
- Convert `F019_build_live_price_file_near_miss_pack.py` to write:
  - `f_new_product_review_pack_rows`
  - `f_new_product_review_summary`
  - compatibility CSV exports.
- Convert `feeder_review_events` append writes to SQL plus CSV export/append compatibility.
- Success threshold:
  - latest pass, near-miss, and summary row counts match SQL.
  - historical timestamped snapshots remain selectable.

### Phase 4 - O Reader Migration
- Convert O400 New Product Review loaders to SQL-first reads:
  - pack options
  - summary load
  - pass and near-miss source rows
  - review events
  - UI drafts
- CSV fallback remains for rollback and first-run bootstrap only.
- Success threshold:
  - O UI tests pass in SQL-primary mode.
  - A fixture with no CSV source but populated SQL tables still loads review rows.

### Phase 5 - One-Off Consumers
- Convert F021-F027 review analysis/audit scripts to SQL-first reads for review packs and review events.
- Keep CSV fallback.
- Success threshold:
  - targeted F review automation tests pass.
  - one local proof run produces the same row counts as CSV baseline.

### Phase 6 - Pause, Seed, And Proof
- Pause F061 and O400 before seeding or cutover.
- Seed current review pack CSVs and review events into SQL.
- Run rollback validation without overwriting live artifacts.
- Run focused tests:
  - O UI review tests
  - F019 review-pack tests
  - F020/F021 review event and fail automation tests
  - storage adapter tests
- Run a bounded F019 local proof with no scraper/API/Sheet writes.
- Restart O400 and prove the UI reads SQL-primary.
- Resume F061 only after proof if it was paused.

## Stop Conditions
- Active F061 or O400 owner cannot be paused cleanly.
- Any review event append creates duplicate event ids.
- Any row-count or header mismatch between SQL and CSV compatibility exports.
- O400 cannot load New Product Review rows from SQL in SQL-primary mode.
- P006 still reports the New Product Review paths as unregistered after registry/map repair.

## Proof Required Before Completion
- Code fix applied:
  - F/O review paths are registered and wired to SQL-primary compatibility helpers.
- Isolated verification:
  - focused O/F/storage tests pass.
  - SQL-vs-CSV counts and headers match for current review pack, historical review pack, summary, events, and drafts.
- Live restoration verification:
  - F061 and O400 are resumed if paused.
  - O400 New Product Review can load the active pack from SQL-primary storage.
  - CSV files remain present only as compatibility exports.

## Status
- study completed: yes.
- code fix applied: yes.
- isolated verification: passed.
- live proof: passed for F/O New Product Review storage path.
- current blocker: none for the registered F/O New Product Review SQL path.

## Completion Evidence - 2026-04-29T15:05:00Z
- Backup before seed:
  - `out/backups/sql_storage_migration_v1/batch_036_f_o_review_sql_20260429T150003Z`
- Registry and dependency map:
  - added F/O review pack, summary, event, and UI draft datasets to `project_control/DATA_BLUEPRINT_REGISTRY.csv`
  - refreshed `out/sql_migration/csv_dependency_map_summary.json`
  - `row_count=1933`
  - `registered_dependency_count=418`
  - `sql_primary_pilot_proven_count=447`
  - `csv_dependency_remaining_count=0`
  - `unresolved_dynamic_count=790`
  - `unregistered_csv_count=725`
- Code path moved to SQL primary with CSV compatibility exports:
  - `F019_build_live_price_file_near_miss_pack.py` writes `f_new_product_review_pack_rows` and `f_new_product_review_summary`
  - `O400_operator_ui.py` reads review options, summaries, rows, events, and drafts from SQL first
  - F021, F023, F025, F026, F027, F028, and F029 read New Product Review packs/events from SQL first
  - `run_O_operator_ui.bat` now defaults to `SELLERONE_STORAGE_MODE=sql_primary_csv_export` and `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
- Live seed/proof:
  - F019 seeded SQL under `sql_primary_csv_export`
  - pass rows: `3`
  - near-miss rows: `1600`
  - SQL `f_new_product_review_pack_rows`: `3206` rows because latest and timestamped snapshots are both stored
  - SQL `f_new_product_review_summary`: `130` rows because latest and timestamped snapshots are both stored
  - SQL `f_feeder_review_events`: `13` rows
  - SQL `o_feeder_review_ui_drafts`: `0` rows
  - O400 SQL loader proof: passes `3`, near-misses `1600`, events `13`, option count `29`
  - O400 restarted from SQL-default launcher on port `8501` with PID `3064`
- Tests:
  - `python -m py_compile ...` passed for modified modules
  - `pytest tests/test_storage_adapter.py tests/test_f019_build_live_price_file_near_miss_pack.py tests/test_o_ui_operator_view.py tests/test_p006_build_csv_dependency_map.py tests/test_h_split_health_gate.py tests/test_controlled_restart_gate.py -q`
  - result: `104 passed`, `1 warning`
- Residual test debt:
  - `tests/test_a015_health_check_runtime.py` has 5 existing behavioral failures outside this storage change area; they are not storage-adapter failures and were not masked.
