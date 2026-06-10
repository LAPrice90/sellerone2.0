# Coding Plan

Date: 2026-04-28
Scope: System-wide migration from CSV-first storage to SQL-first storage, starting with backup and full runtime pause planning.

## 1) Phase Summary

| Phase | Goal | Allowed files | Tests | Live proof needed | Status |
|---|---|---|---|---|---|
| Phase 0 | Full pause and backup preparation | `plans/active/sql-storage-migration-v1/*`, later backup scripts only | plan review only, then backup manifest tests | yes | planned |
| Phase 1 | Schema and storage-adapter design | `scripts/core/storage/*`, tests, plan files | unit tests only | no | planned |
| Phase 2 | SQL shadow mode | storage scripts, tests, migration artifacts | seed/export/reconcile tests | yes | planned |
| Phase 3 | B flow SQL primary pilot | B storage touchpoints only | B tests and B proof | yes | planned |
| Phase 4 | A flow SQL primary | A storage touchpoints only | A tests and A proof | yes | planned |
| Phase 5 | E flow SQL primary | E storage touchpoints only | E tests and E proof | yes | planned |
| Phase 6 | H flow SQL primary | H storage touchpoints only | H tests and controlled H proof | yes | planned |
| Phase 7 | Retire obsolete CSV dependencies | approved files only | full scoped regression by flow | yes | planned |
| Batch 037 | O/F contract IO SQL expansion | O/F contract helpers, O/F contract writers/readers, P006, tests | targeted O/F/P006 tests | yes | completed |
| Batch 038 | B finance/order SQL expansion | B finance IO helper, B001/B002/B003/B004/B007/B024/B032, registry, P006 | targeted B/P006 tests, SQL seed, B maintenance proof | yes | completed |
| Batch 039 | Product DB SQL contract and repricer tracker UI read model | Product DB contract helper, P008, O030/O050/O450/O400/O runner, O schemas, tests | targeted Product DB/O tests and local proof scripts | no live-owner proof | completed |
| Batch 040 | Product DB scanner link simulation | P009 read-only simulator, targeted tests, control files | targeted Product DB/P009 tests and read-only local proof | no live-owner proof | completed |
| Batch 041 | Product DB duplicate header source/export repair | Product DB contract helper, A/B Product DB preview exporters, targeted tests, local preview repair | targeted Product DB tests and local P008/P009/O030 proof | no live-owner proof | completed |
| Batch 042 | Product DB review pack | P010 read-only review pack, duplicate-ASIN/scanner review outputs, targeted tests, registry/control files | targeted Product DB/P009/P010 tests and local review output proof | no live-owner proof | completed |
| Batch 043 | Scanner Product DB SQL inserts | P011 scanner insert script, Product DB validator/classification updates, SQL/local mirror proof, targeted tests | targeted Product DB/P009/P010/P011 tests and local SQL proof | no live-owner proof | completed |
| Batch 044 | Scanner identity uniqueness proof | P012 scanner identity check, proof outputs, registry/control files, targeted tests | targeted scanner/Product DB tests and local proof output | no live-owner proof | completed |
| Batch 045 | Repricer write-status proof summary | P013 read-only repricer proof, root-cause output, registry/control files, targeted tests | targeted P013/O050 tests and local proof output | no H owner proof | completed |
| Batch 046 | WRITE_NOT_APPLIED contract acceptance | O050/P013 allowed status update, Product DB contract, targeted tests, local O read-model rebuild | targeted P013/O050 tests and local proof output | no H owner proof | completed |
| Batch 047 | H source blank write-status normalization | H runtime snapshot source, H130 parked status, P013/O050 stale-audit proof handling, targeted tests, control files | targeted H split health/P013/O050 tests | H-owned proof required | completed with stale audit warnings |

## 2) Phase Details

### Phase 0 - Full Pause And Backup Preparation
Goal:
- Make a safe migration boundary before any live data movement.
- Pause every running system and API caller before backup, seed, or cutover.
- Build a backup manifest that can prove exactly what was backed up.

Files allowed to change:
- `plans/active/sql-storage-migration-v1/*`
- Later only after approval for Batch 001 implementation: a dedicated backup/manifest script under `scripts/one_off/` or `scripts/tools/`

Implementation tasks:
- Document the pause checklist for A, B, E, H, O, Feeder, API collection, home-time monitor, and controlled restart ownership.
- Define proof checks for process state, lock files, owner markers, and log movement.
- Build backup manifest tooling in a later batch.
- Backup code, config, data, out artifacts, reference inputs, plan files, and secrets policy metadata.

Isolated verification:
- command: plan review only in this batch
- expected result: plan files clearly define pause, backup, rollback, and proof boundaries

Monitored validation:
- live proof needed: yes, before actual backup or migration
- forced proof window: explicit full pause window approved by user
- artifacts to poll: process list, lock files under `out/` and `out/locks/`, B/H owner markers, recent log mtimes
- poll cadence: immediate preflight, then every 2 minutes during the pause window
- success threshold: no active owner process and no protected artifact writes observed during the quiet window
- timeout rule: park if any owner cannot be stopped or any artifact keeps moving unexpectedly
- fallback if forced proof is blocked: document the active owner and wait for or request a safe shutdown window
- next automatic step after success: run backup manifest only
- notification mode: interrupt user only if pause fails, a new FAIL appears, or approval is needed
- user interruption threshold: active owner cannot be paused, evidence contradicts pause state, or destructive scope would be needed

Phase status:
- code fix applied: yes - 2026-04-28T12:02:47Z - added `scripts/one_off/P003_build_sql_migration_backup_manifest.py`, focused tests, and this runbook.
- isolated verification passed: yes - `python -m pytest tests/test_p003_build_sql_migration_backup_manifest.py tests/test_p002_plan_forced_proof_window.py` passed 12 tests.
- monitored validation: passed - 2026-04-28T12:37:25Z - elevated pause completed, scheduled tasks were disabled, stale dead-PID locks were archived, 120-second quiet check passed, registry manifest was written, 51 registry files were copied, and 51 copied hashes matched manifest hashes. Backup bundle: `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z`.

### Phase 1 - Schema And Storage-Adapter Design
Goal:
- Define SQL schemas and one storage API before changing flow scripts.

Files allowed to change:
- `scripts/core/storage/*`
- `tests/test_storage_*`
- `plans/active/sql-storage-migration-v1/*`
- `project_control/DATA_BLUEPRINT_REGISTRY.csv` only if adding SQL metadata rows is explicitly approved

Implementation tasks:
- Create connection configuration with PostgreSQL as production target and SQLite test support.
- Add storage-mode flags: `csv`, `sql_shadow`, `sql_primary_csv_export`.
- Define table contracts for first migration group.
- Define transaction, append, upsert, and export helpers.

Isolated verification:
- command: `pytest tests/test_storage_*`
- expected result: storage API tests pass without live DB dependency

Monitored validation:
- live proof needed: no
- forced proof window: not needed
- artifacts to poll: none
- poll cadence: none
- success threshold: unit tests pass
- timeout rule: not applicable
- fallback if forced proof is blocked: not applicable
- next automatic step after success: Phase 2 SQL shadow tooling
- notification mode: final or phase-complete only
- user interruption threshold: schema decision requires user approval

Phase status:
- code fix applied: yes - added `scripts/core/storage/` adapter/config package and Batch 002 plan file.
- isolated verification passed: yes - `python -m pytest tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py` passed 13 tests.
- monitored validation: not needed

### Phase 2 - SQL Shadow Mode
Goal:
- Load SQL from CSV while CSV remains runtime authority.

Files allowed to change:
- `scripts/core/storage/*`
- `scripts/tools/*storage*`
- `tests/test_storage_*`
- plan files

Implementation tasks:
- Build CSV-to-SQL seed tool.
- Build SQL-to-CSV export tool.
- Build reconciliation reports for row counts, keys, totals, timestamps, and hashes.
- Do not alter flow scripts yet.

Isolated verification:
- command: storage seed/export/reconcile tests
- expected result: fixture CSVs round-trip through SQL without loss

Monitored validation:
- live proof needed: yes, against backed-up artifacts only
- forced proof window: full paused migration window
- artifacts to poll: backup manifest, reconciliation report, SQL seed summary
- poll cadence: after each seed group
- success threshold: all critical datasets reconcile or have named approved exceptions
- timeout rule: park on first unexplained mismatch
- fallback if forced proof is blocked: stay in CSV authority mode
- next automatic step after success: Phase 3 B pilot design
- notification mode: interrupt only on mismatch, new FAIL, or approval need
- user interruption threshold: reconciliation mismatch without clear root cause

Phase status:
- code fix applied: yes - added `scripts/one_off/P004_seed_sql_shadow_from_manifest.py` and Batch 003 plan file.
- isolated verification passed: yes - `python -m pytest tests/test_p004_seed_sql_shadow_from_manifest.py tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py` passed 17 tests.
- monitored validation: passed for frozen registry backup - seeded 45 shadow tables and 424,784 rows into `out/backups/sql_storage_migration_v1/sql_storage_migration_v1_20260428T123430Z/shadow.sqlite3`; `B.ORDERS_ALL` export row count matched manifest row count 10,450.

### Phase 3 - B Flow SQL Primary Pilot
Goal:
- Move B-owned pilot datasets to SQL primary with CSV compatibility exports.

Files allowed to change:
- B-owned scripts named in the approved batch
- B tests
- storage adapter files
- plan files

Implementation tasks:
- Choose a small B pilot group, likely tokens or order-master support tables after ownership review.
- Write SQL transaction first.
- Export CSV only after transaction success.
- Keep rollback to CSV mode available.

Isolated verification:
- command: B-scoped tests for touched files
- expected result: B tests pass

Monitored validation:
- live proof needed: yes
- forced proof window: B maintenance handoff, then `B_RUN_ONCE=1` proof cycle
- artifacts to poll: B manifest, B checklist, SQL reconciliation report, CSV export timestamps
- poll cadence: after B finalization only
- success threshold: B run finalized, B-scoped health fresh, SQL and CSV exports reconcile
- timeout rule: park if B cannot enter maintenance or proof run does not finalize
- fallback if forced proof is blocked: keep B in CSV mode
- next automatic step after success: A migration planning
- notification mode: interrupt only on FAIL, mismatch, blocked maintenance, or approval need
- user interruption threshold: active B owner cannot safely hand off

Phase status:
- code fix applied: yes - Batch 005 converted `B.TOKEN_COGS_LEDGER`; Batch 006 converted B010 token ops outputs `b_token_movement_log` and `b_order_cogs_from_tokens`; Batch 007 converted B014 token checklist `b_token_daily_checklist`; default mode remains `csv`.
- isolated verification passed: yes - latest command `python -m pytest tests/test_b014_build_token_daily_checklist.py tests/test_b010_build_token_ops_outputs.py tests/test_b025_build_token_cogs_ledger.py tests/test_p005_reconcile_sql_shadow.py tests/test_p004_seed_sql_shadow_from_manifest.py tests/test_storage_adapter.py tests/test_p003_build_sql_migration_backup_manifest.py` passed 25 tests.
- monitored validation: partially confirmed - supervised `B_RUN_ONCE=1` proof run `B_20260428T125631Z` finalized with `B_EXIT rc=0` and confirmed B025 SQL/CSV row-count match `11817`; direct local proofs confirmed B010 and B014 SQL/CSV row-count matches with Sheets disabled. Whole B flow health remains not green because the proof run reported existing `FAIL=1` and `WARN=3`.

### Phase 4 - A Flow SQL Primary
Goal:
- Move A-owned inventory, stock, fees, and health-source datasets after B pilot proves the pattern.

Files allowed to change:
- A-owned scripts named in approved batch
- A tests
- storage adapter files
- plan files

Implementation tasks:
- Convert one A dataset group at a time.
- Preserve staged publish behavior.
- Keep CSV compatibility exports.

Isolated verification:
- command: A-scoped tests for touched files
- expected result: A tests pass

Monitored validation:
- live proof needed: yes
- forced proof window: owned A cycle path after all active owners are paused or handed off
- artifacts to poll: A manifest, A checklist, SQL reconciliation report
- poll cadence: after A finalization only
- success threshold: A run finalized, A-scoped health fresh, SQL and CSV exports reconcile
- timeout rule: park if A proof cannot complete safely
- fallback if forced proof is blocked: keep A in CSV mode
- next automatic step after success: E migration planning
- notification mode: interrupt only on FAIL, mismatch, blocked handoff, or approval need
- user interruption threshold: stale health conflicts with newer runtime evidence

Phase status:
- code fix applied: yes - Batch 008 converted A006 stock events local output `a_stock_events_raw`; default mode remains `csv`, and proof ran with Sheets disabled.
- isolated verification passed: yes - `python -m pytest tests/test_a006_build_stock_events_raw.py tests/test_storage_adapter.py` passed 8 tests; broader migration regression command passed 26 tests.
- monitored validation: local runtime proof passed - `A006_build_stock_events_raw.py` wrote SQL table `a_stock_events_raw` row count `6033`, matching CSV export `out/stock_events_raw.csv` row count `6033`; no Sheet writes were performed.

### Phase 5 - E Flow SQL Primary
Goal:
- Move E analytics outputs to SQL primary after A/B sources are stable.

Files allowed to change:
- E-owned scripts named in approved batch
- E tests
- storage adapter files
- plan files

Implementation tasks:
- Convert sales velocity, ROI, restock signals, and performance summary by dataset group.
- Keep E publish exports unchanged until proven.

Isolated verification:
- command: E-scoped tests for touched files
- expected result: E tests pass

Monitored validation:
- live proof needed: yes
- forced proof window: owned E cycle once
- artifacts to poll: E manifest, E checklist, SQL reconciliation report
- poll cadence: after E finalization only
- success threshold: E run finalized, E-scoped health fresh, SQL and CSV exports reconcile
- timeout rule: park if E proof cannot complete safely
- fallback if forced proof is blocked: keep E in CSV mode
- next automatic step after success: H migration planning
- notification mode: interrupt only on FAIL, mismatch, blocked owner, or approval need
- user interruption threshold: E output freshness or reconciliation conflict

Phase status:
- code fix applied: yes - Batch 009 converted E001 sales velocity local output `e_sku_sales_velocity`; default mode remains `csv`.
- isolated verification passed: yes - `python -m pytest tests/test_e001_build_sales_velocity.py tests/test_storage_adapter.py` passed 8 tests; broader migration regression command passed 27 tests.
- monitored validation: passed - owned E cycle ran with SQL-primary mode, Sheets disabled, cadence disabled for proof; E split health reported `0 FAIL` and `0 WARN`; SQL table `e_sku_sales_velocity` row count `483` matched CSV export `out/sku_sales_velocity.csv` row count `483`.

### Phase 6 - H Flow SQL Primary
Goal:
- Move H runtime and repricing intelligence datasets only after lower-risk flows prove the SQL pattern.

Files allowed to change:
- H-owned scripts named in approved batch
- H tests
- storage adapter files
- plan files

Implementation tasks:
- Pause H scheduler ownership.
- Confirm no active H owner remains.
- Convert one H dataset group at a time.
- Keep CSV fallback until live-loop proof is confirmed.

Isolated verification:
- command: H-scoped tests for touched files
- expected result: H tests pass

Monitored validation:
- live proof needed: yes
- forced proof window: guarded H controlled one-shot, H-scoped health after terminal markers, then scheduler resume
- artifacts to poll: H terminal info, H checklist, H runtime status, scheduler ownership markers, SQL reconciliation report
- poll cadence: after controlled run finalization, then after ownership resume
- success threshold: controlled run terminal, H-scoped health fresh, owner restored, SQL and CSV exports reconcile
- timeout rule: park if H owner cannot be paused or restored
- fallback if forced proof is blocked: keep H in CSV mode
- next automatic step after success: CSV dependency retirement planning
- notification mode: interrupt only on FAIL, mismatch, owner restoration failure, or approval need
- user interruption threshold: repricing safety or ownership contradiction

Phase status:
- code fix applied: yes - Batch 010 converted H004 market snapshot/history local outputs `h_hos_daily_market_snapshot` and `h_hos_daily_market_history`; default mode remains `csv`.
- isolated verification passed: yes - `python -m pytest tests/test_h004_build_daily_market_snapshot.py tests/test_storage_adapter.py` passed 8 tests; broader migration regression command passed 28 tests.
- monitored validation: local runtime proof passed - direct H004 proof ran with SQL-primary mode; SQL table `h_hos_daily_market_snapshot` row count `65` matched latest CSV row count `65`; SQL table `h_hos_daily_market_history` row count `162` matched CSV row count `162`. H pricing loop was not started or modified.

### Phase 7 - Retire Obsolete CSV Dependencies
Goal:
- Remove only proven obsolete CSV reads and writes.

Files allowed to change:
- approved scripts from each flow after proof
- tests
- docs and plan files

Implementation tasks:
- Keep CSV exports for publish snapshots, rollback, human review, and external compatibility.
- Remove or block only stale-risk CSV dependencies that SQL has replaced.
- Update data blueprint and runbooks.

Isolated verification:
- command: scoped tests for every touched flow
- expected result: all touched flow tests pass

Monitored validation:
- live proof needed: yes
- forced proof window: each flow-owned proof path
- artifacts to poll: manifests, scoped checklists, reconciliation reports, publish snapshots
- poll cadence: after each owner flow finalizes
- success threshold: no unresolved FAIL, approved WARNs only, rollback snapshots present
- timeout rule: park pending next proof window if a flow cannot prove safely
- fallback if forced proof is blocked: keep CSV compatibility in place
- next automatic step after success: archive plan
- notification mode: milestone only
- user interruption threshold: hidden dependency found or rollback proof fails

Phase status:
- code fix applied: yes - Batch 011 added `scripts/one_off/P006_build_csv_dependency_map.py` and output schema validation for the CSV dependency map.
- isolated verification passed: yes - `python -m pytest tests/test_p006_build_csv_dependency_map.py` passed 2 tests.
- monitored validation: report written - latest `out/sql_migration/csv_dependency_map.csv` has `1271` CSV calls, `187` registered dependencies, `94` SQL-primary pilot-proven calls, `101` remaining registered CSV dependencies, `796` unresolved dynamic calls, and `288` unregistered CSV calls. This is mapping only; no CSV dependency was retired yet.

### Phase 5 Follow-up - E002 ROI Snapshot Expansion
Goal:
- Expand E-flow SQL-primary coverage to ROI snapshot outputs.

Files changed:
- `scripts/flows/E/E002_build_roi_snapshot.py`
- `tests/test_e002_build_roi_snapshot.py`
- plan files

Phase status:
- code fix applied: yes - Batch 012 converted `e_sku_roi_snapshot`, `e_sku_roi_snapshot_uk`, `e_sku_roi_snapshot_non_uk`, and `e_sku_roi_snapshot_by_country`.
- isolated verification passed: yes - `python -m pytest tests/test_e002_build_roi_snapshot.py tests/test_storage_adapter.py` passed 13 tests; broader migration regression command passed 36 tests.
- monitored validation: passed - owned E cycle ran with SQL-primary mode, Sheets disabled, cadence disabled for proof; E split health reported `0 FAIL` and `0 WARN`; all four ROI SQL row counts matched their CSV exports.

### Phase 5 Follow-up - E003/E004/E005 Analytics Expansion
Goal:
- Expand E-flow SQL-primary coverage to restock, performance summary, and study report outputs.

Files changed:
- `scripts/flows/E/E003_build_restock_signals.py`
- `scripts/flows/E/E004_build_performance_summary.py`
- `scripts/flows/E/E005_build_study_report.py`
- `tests/test_e003_build_restock_signals.py`
- `tests/test_e004_build_performance_summary.py`
- `tests/test_e005_build_study_report.py`
- plan files

Phase status:
- code fix applied: yes - Batch 013 converted `e_sku_restock_signals`, `e_sku_performance_summary`, and `e_study_report`.
- isolated verification passed: yes - focused E003/E004/E005/storage tests passed 14 tests; broader migration regression command passed 43 tests.
- monitored validation: passed - owned E cycle ran with SQL-primary mode, Sheets disabled, cadence disabled for proof; E split health reported `0 FAIL` and `0 WARN`; all three new SQL row counts matched their CSV exports.

### Phase 5 Follow-up - E006/E007 Sales Truth Expansion
Goal:
- Expand E-flow SQL-primary coverage to sales truth reconciliation and daily sales truth outputs.

Files changed:
- `scripts/flows/E/E006_build_sales_truth_reconciliation.py`
- `scripts/flows/E/E007_build_sku_daily_sales_truth.py`
- `tests/test_e006_build_sales_truth_reconciliation.py`
- `tests/test_e007_build_sku_daily_sales_truth.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 014 converted `e_sales_truth_sku_30d`, `e_sales_truth_reconciliation`, and `e_sku_daily_sales_truth`.
- isolated verification passed: yes - focused E006/E007/storage tests passed 17 tests; broader migration regression passed 38 tests with `PYTHONPATH` set to the repo root.
- monitored validation: passed - owned E cycle ran with SQL-primary mode, Sheets disabled, cadence disabled for proof; E split health reported `0 FAIL` and `0 WARN`; all three new SQL row counts matched their CSV exports.

### Phase 3 Follow-up - B012 Token Events Expansion
Goal:
- Expand B-flow SQL-primary coverage to the append-only token event log.

Files changed:
- `scripts/flows/B/B012_build_token_events_append.py`
- `tests/test_b012_build_token_events_append.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 015 converted `b_token_events` in SQL-primary mode while preserving default CSV append behavior.
- isolated verification passed: yes - focused B012/storage tests passed 9 tests; broader migration regression passed 40 tests with `PYTHONPATH` set to the repo root.
- monitored validation: local runtime proof passed - direct B012 run wrote SQL table `b_token_events` row count `92644`, matching CSV export `out/token_events.csv` row count `92644`, with Sheet writes disabled. Full B-cycle proof was not run because B012 is not in the current B cycle run order and a full B run would not prove this script.

### Phase 3 Follow-up - B004 Diagnostic Outputs Expansion
Goal:
- Expand B-flow SQL-primary coverage to B004 diagnostic outputs while leaving the main order-master output unchanged.

Files changed:
- `scripts/flows/B/B004_build_order_master.py`
- `tests/test_b004_level_gate.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 016 converted `b_orders_missing_tokens`, `b_l1_missing_fee_keys`, and `b_l3_orphans`; B004 standalone import bootstrapping was fixed.
- isolated verification passed: yes - focused B004/storage tests passed 15 tests; broader migration regression passed 48 tests with `PYTHONPATH` set to the repo root.
- monitored validation: local runtime proof passed - direct B004 run wrote SQL row counts matching CSV exports for all three diagnostic outputs. Full B-cycle proof was not run because the direct proof verified the local outputs without widening into B cycle API/Sheet-capable steps.

### Phase 3 Follow-up - B004 Order Master Expansion
Goal:
- Expand B-flow SQL-primary coverage to the main order-master output.

Files changed:
- `scripts/flows/B/B004_build_order_master.py`
- `tests/test_b004_level_gate.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 017 converted `b_order_master`; CSV compatibility export and previous snapshot behavior remain in place.
- isolated verification passed: yes - focused B004/storage tests passed 15 tests; broader migration regression passed 48 tests with `PYTHONPATH` set to the repo root.
- monitored validation: local runtime proof passed - direct B004 run wrote SQL table `b_order_master` row count `10183`, matching CSV export `out/order_master.csv` row count `10183`, with Sheet writes disabled. Full B-cycle proof was not run because the direct proof verified the local output without widening into B cycle API/Sheet-capable steps.

### Phase 3 Follow-up - B006 FX Ledgers Expansion
Goal:
- Expand B-flow SQL-primary coverage to FX-normalized ledgers and the FX-rate cache.

Files changed:
- `scripts/flows/B/B006_build_fx_ledgers.py`
- `tests/test_b006_build_fx_ledgers.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 018 converted `b_order_ledger_fx`, `b_financial_ledger_fx`, and `b_fx_rates_daily`.
- isolated verification passed: yes - focused B006/storage tests passed 9 tests; broader migration regression passed 50 tests with `PYTHONPATH` set to the repo root.
- monitored validation: local runtime proof passed - direct B006 run wrote SQL row counts matching CSV exports for all three outputs. The local FX cache already covered all current date/currency pairs, so proof did not need an external FX API call.

### Phase 3 Follow-up - B008 Refund Token Events Expansion
Goal:
- Expand B-flow SQL-primary coverage to the refund token event log.

Files changed:
- `scripts/flows/B/B008_apply_refunds_to_tokens.py`
- `tests/test_b008_apply_refunds_to_tokens.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 019 converted `b_refund_token_events` and fixed the local event-log writer so it does not duplicate newly written rows.
- isolated verification passed: yes - focused B008/storage tests passed 9 tests; broader migration regression passed 52 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing refund event log was written to SQL with row count `19`, matching CSV export `out/refund_token_events.csv` row count `19`. Full B008 was not run because current source has `172` pending refund rows and running it would mutate `token_ledger_live`.

### Phase 3 Follow-up - B009 Stock Adjustment Token Events Expansion
Goal:
- Expand B-flow SQL-primary coverage to the stock-adjustment token event log.

Files changed:
- `scripts/flows/B/B009_apply_stock_adjustments_to_tokens.py`
- `tests/test_b009_apply_stock_adjustments_to_tokens.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 020 converted `b_stock_adjustment_token_events`.
- isolated verification passed: yes - focused B009/storage tests passed 11 tests; broader migration regression passed 56 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing stock-adjustment event log was written to SQL with row count `14096`, matching CSV export `out/stock_adjustment_token_events.csv` row count `14096`. Full B009 was not run because current source has `246` pending stock-adjustment base events and running it would mutate `token_ledger_live`.

### Phase 3 Follow-up - B003 Financial Events Level 3 Official Expansion
Goal:
- Expand B-flow SQL-primary coverage to the official Level 3 financial-events artifact.

Files changed:
- `scripts/flows/B/B003_run_financial_events_level3.py`
- `tests/test_b003_run_financial_events_level3.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 021 converted `b_financial_events_level3_official`.
- isolated verification passed: yes - focused B003/storage tests passed 9 tests; broader migration regression passed 58 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing official Level 3 artifact was written to SQL with row count `10155`, matching CSV export `out/financial_events_level3_official.csv` row count `10155`. Full B003 was not run because it can call SP-API and write Sheet/Product_DB side effects.

### Phase 4 Follow-up - A004 Fee Outputs Expansion
Goal:
- Expand A-flow SQL-primary coverage to A004 fee outputs without running the live SP-API fee collector or writing Google Sheets.

Files changed:
- `scripts/flows/A/A004_run_fees_to_sheet.py`
- `tests/test_a004_fee_requeue.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 022 converted `a_fees_latest`, `a_fees_failed`, and local table `a_fees_estimates`; `product_db_preview.csv` remains CSV-only because it has several other writers.
- isolated verification passed: yes - focused A004/storage tests passed 12 tests; broader migration regression passed 63 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing A004 fee artifacts were written to SQL with row counts matching CSV exports: `a_fees_estimates` `88`, `a_fees_latest` `88`, and `a_fees_failed` `0`. Full A004 was not run because it can call SP-API and write Google Sheets/Product_DB side effects.

### Phase 4 Follow-up - A005 Inventory Report Outputs Expansion
Goal:
- Expand A-flow SQL-primary coverage to A005 local inventory report outputs without running the live SP-API report collector.

Files changed:
- `scripts/flows/A/A005_run_inventory_adjustments_report.py`
- `tests/test_a005_inventory_adjustments_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 023 converted `a_inventory_ledger_raw`, `a_inventory_adjustments_latest`, and future fallback table `a_inventory_adjustments_raw`.
- isolated verification passed: yes - focused A005/storage tests passed 11 tests; broader migration regression passed 67 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing A005 artifacts were written to SQL with row counts matching CSV exports: `a_inventory_ledger_raw` `6033` and `a_inventory_adjustments_latest` `6033`. The fallback raw adjustments file was not present and was not created just for proof. Full A005 was not run because it can call SP-API report endpoints.

### Phase 4 Follow-up - Stock Receipts Latest Expansion
Goal:
- Expand A-owned stock receipt latest output to SQL-primary storage without running the Google Sheets stock receipt processor.

Files changed:
- `scripts/tools/process_stock_receipts_sheet.py`
- `tests/test_process_stock_receipts_sheet.py`
- `scripts/flows/B/B004_build_order_master.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 024 converted `a_stock_receipts_latest` and local table `a_stock_receipt_summary`; empty stock receipt outputs now retain stable headers.
- isolated verification passed: yes - focused stock receipt/storage tests passed 11 tests; broader migration regression passed 71 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing stock receipt artifacts were written to SQL with row counts matching CSV exports: `a_stock_receipt_summary` `0` and `a_stock_receipts_latest` `0`, each with `11` columns. Full stock receipt processing was not run because it can read/write Google Sheets and append token ledger rows. B004 proof support was tightened so a zero-second L1 stability window disables the guard instead of causing a false recently-modified block.

### Phase 4 Follow-up - Inbound Shipment Contents Expansion
Goal:
- Expand shared inbound shipment contents output to SQL-primary storage without running live SP-API inbound collectors.

Files changed:
- `scripts/flows/B/B030_run_inbound_shipment_contents_report.py`
- `scripts/flows/B/B031_run_inbound_shipment_items.py`
- `tests/test_inbound_shipment_contents_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 025 converted both producer paths for `sys_inbound_shipment_contents` and local raw table `sys_inbound_shipment_contents_raw`.
- isolated verification passed: yes - focused inbound/storage tests passed 10 tests; broader migration regression passed 74 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing inbound shipment artifacts were written to SQL with row counts matching CSV exports: `sys_inbound_shipment_contents` `47` and `sys_inbound_shipment_contents_raw` `47`, each with `3` columns. Full inbound collectors were not run because they call SP-API.

### Phase 4 Follow-up - Product DB Preview Expansion
Goal:
- Expand shared Product DB preview output to SQL-primary storage across all current producers without running API or Sheet-writing flows.

Files changed:
- `scripts/core/storage/pandas_bridge.py`
- `scripts/core/storage/__init__.py`
- `scripts/flows/A/A001_run_listings_to_sheet.py`
- `scripts/flows/A/A002_run_catalog_items_to_sheet.py`
- `scripts/flows/A/A003_run_inventory_to_sheet.py`
- `scripts/flows/A/A004_run_fees_to_sheet.py`
- `scripts/flows/B/B001_run_orders_to_sheet.py`
- `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
- `scripts/flows/B/B003_run_financial_events_level3.py`
- `tests/test_storage_adapter.py`
- `tests/test_product_db_preview_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 026 converted all seven current producer paths for `sys_product_db_preview`.
- isolated verification passed: yes - focused Product DB/storage tests passed 10 tests; broader migration regression passed 77 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing Product DB preview was written to SQL with row count `608`, matching CSV export `out/product_db_preview.csv` row count `608`, with `72` columns. Full producer flows were not run because they can call SP-API and/or write Google Sheets.

### Phase 3 Follow-up - B Order Archive Expansion
Goal:
- Expand B order and order-item archive outputs to SQL-primary storage without running live order collectors or backfill jobs.

Files changed:
- `scripts/flows/B/B001_run_orders_to_sheet.py`
- `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
- `scripts/one_off/T019_D020_backfill_missing_orders_from_sellerboard.py`
- `tests/test_b_orders_archive_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 027 converted current registered writer paths for `b_orders_all` and `b_order_items_all`.
- isolated verification passed: yes - focused B order archive/storage tests passed 11 tests; broader migration regression passed 80 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing B order archives were written to SQL with row counts matching CSV exports: `b_orders_all` `10451` and `b_order_items_all` `10473`. Full order collectors/backfills were not run because they can call SP-API and mutate archive files.

### Phase 3 Follow-up - Token Live Files Expansion
Goal:
- Expand live token ledger and token allocation outputs to SQL-primary storage without running token mutation one-off scripts.

Files changed:
- `scripts/one_off/T002_B015_fix_duplicate_token_ids.py`
- `scripts/one_off/T009_B031_backfill_tokens_from_orders_sheet.py`
- `scripts/one_off/T010_B034_full_rebuild_tokens_from_orders_sheet.py`
- `tests/test_b_token_live_storage.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 028 converted current registered one-off writer paths for `b_token_ledger_live` and `b_token_allocations_live`.
- isolated verification passed: yes - focused token live/storage tests passed 11 tests; broader migration regression passed 83 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - current existing token live files were written to SQL with row counts matching CSV exports: `b_token_ledger_live` `13594` and `b_token_allocations_live` `11813`. Token mutation one-offs were not run.

### Cross-Flow Follow-up - SQL-First Reader Migration
Goal:
- Convert remaining registered CSV reader dependencies to SQL-first reads with CSV fallback.

Files changed:
- `scripts/core/storage/pandas_bridge.py`
- `scripts/core/storage/__init__.py`
- `scripts/flows/A/A004_run_fees_to_sheet.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- `scripts/flows/B/B007_allocate_tokens_live.py`
- `scripts/flows/B/B024_build_tokens_november_anchor.py`
- `scripts/flows/D/D009_backdate_tokens_all.py`
- `scripts/flows/E/E001_build_sales_velocity.py`
- `scripts/flows/E/E003_build_restock_signals.py`
- `scripts/flows/E/E004_build_performance_summary.py`
- `scripts/one_off/T001_B011_build_token_tests_daily.py`
- `scripts/one_off/T017_D010_add_legacy_tokens.py`
- `scripts/tools/diff_active_vs_scope.py`
- `tests/test_storage_adapter.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- plan files

Phase status:
- code fix applied: yes - Batch 029 added SQL-first reader support and seeded `a_inventory_summaries`, `a_inventory_history`, `b_phase1_sku_scope`, `h_listing_offer_history`, and `h_seller_of_interest`.
- isolated verification passed: yes - touched files compile and broad migration regression passed 91 tests with `PYTHONPATH` set to the repo root.
- monitored validation: guarded local storage proof passed - dependency map reports `csv_dependency_remaining_count=0`. No live A015 run, API collectors, Sheet writers, or token mutation scripts were run.

### Cross-Flow Follow-up - Rollback Export Validation And Re-Enable Plan
Goal:
- Prove SQL can export rollback-compatible CSVs without overwriting live artifacts, and document the controlled proof sequence before scheduler restoration.

Files changed:
- `scripts/one_off/P007_validate_sql_rollback_exports.py`
- `tests/test_p007_validate_sql_rollback_exports.py`
- `plans/active/sql-storage-migration-v1/REENABLE_PROOF_PLAN.md`
- plan files

Phase status:
- code fix applied: yes - Batch 030 added rollback export validation for `48` mapped SQL tables.
- isolated verification passed: yes - focused rollback/storage tests passed 11 tests.
- monitored validation: guarded local rollback proof passed - rollback validator exported all mapped tables to a scratch folder and matched row counts, headers, and canonical CSV hashes against live compatibility CSVs: `48 pass`, `0 fail`.
- scheduler restoration: not executed in this batch; proof sequence is documented in `REENABLE_PROOF_PLAN.md`.

### Re-Enable Proof - B-Owned SQL-Primary Local Proof
Goal:
- Run the first B proof window under `sql_primary_csv_export` without live SP-API calls or Google Sheets writes.

Allowed files for this phase:
- `out/sql/sellerone_dev.sqlite3`
- B local output CSV compatibility exports already owned by B.
- `out/sql_migration/*`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- P002 forced proof output: `plans/active/sql-storage-migration-v1/forced_proof_B.json`
- B ownership preflight: no active `python.exe`; no B live or legacy lock; no maintenance markers.
- Full `B_RUN_ONCE=1` is not the first proof because the current B runner includes B001/B002 live order API calls, optional API collections, B011 orphan recovery API calls when orphans exist, and a quiet-mode publish block that can write Sheets.
- Local-safe proof will run B-owned local steps only: token allocation sync, token allocation idempotence, token COGS ledger, Order Master with Sheets disabled, and FX ledgers with existing FX cache preference.

Stop conditions:
- Any token ledger row-count movement outside an explicit token mutation proof.
- Any SQL/CSV row or header mismatch for B-owned proof tables.
- Any attempt to write Google Sheets.
- Any live API call requirement.

Phase status:
- code fix applied: not applicable - proof phase only.
- isolated verification passed: yes - Batch 031 ran B local SQL-primary steps with no SP-API calls and no Sheet writes: B030, B025, B004, and B006. Rollback validation passed `48/48` tables with `0` failures.
- token stability: passed - token ledger and token allocation row counts and hashes were unchanged before and after the proof.
- live loop verification: not yet proven. Full B loop proof remains blocked until live API and Sheet-write scope is explicitly approved or the B runner gets a dedicated no-API/no-Sheets proof mode.

### Re-Enable Proof - E-Owned SQL-Primary Isolated Proof
Goal:
- Run one owned E cycle under `sql_primary_csv_export` while schedulers remain disabled and Sheet publishing remains off.

Allowed files for this phase:
- `out/sql/sellerone_dev.sqlite3`
- E local output CSV compatibility exports.
- E run logs, manifests, and E split health outputs.
- `out/sql_migration/*`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- P002 forced proof output: `plans/active/sql-storage-migration-v1/forced_proof_E.json`
- E ownership preflight: no active E lock; AMZ scheduled tasks disabled.
- Run `scripts/cycles/run_E_cycle.py` with `E_ENFORCE_CADENCE=0`, `E_WRITE_SHEETS=0`, and `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.

Stop conditions:
- Any E cycle failure.
- Any E split health `FAIL`.
- Any SQL/CSV row or header mismatch for E-owned proof tables.
- Any Sheet write attempt.

Phase status:
- code fix applied: yes - Batch 032 fixed `scripts/phase1/phase1_sku_scope.py` so E-scoped A015 daily-intel refresh keeps `b_phase1_sku_scope` in SQL parity with `out/phase1_sku_scope.csv`.
- isolated verification passed: yes - focused tests passed `16`; E owned proof rerun completed all E tasks; E split health had `0 FAIL` and `0 WARN`; rollback validation passed `48/48` tables.
- live loop verification: not yet proven for scheduler restoration. E owned isolated proof is confirmed, but scheduled task restoration has not been performed.

### Re-Enable Proof - H-Owned SQL-Primary Controlled Proof
Goal:
- Run one guarded H controlled proof under `sql_primary_csv_export` while schedulers remain disabled, Sheet publish remains off, and live price writes remain off.

Allowed files for this phase:
- `out/sql/sellerone_dev.sqlite3`
- H local output CSV compatibility exports.
- H live state, logs, scoped health outputs, and rollback proof artifacts.
- `out/sql_migration/*`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- P002 forced proof output: `plans/active/sql-storage-migration-v1/forced_proof_H.json`
- H preflight found no live Python owner process and all AMZ scheduled tasks disabled.
- H stale run marker exists for run id `20260428T121555Z`; use `run_H_isolation_pause.bat` and guarded H isolation reconcile paths instead of manual deletion.
- Run `run_H_isolation_success.bat` with SQL primary storage, Sheet publish disabled, live write disabled, and no scheduler restoration.

Stop conditions:
- Any Sheet write attempt.
- Any live price write attempt.
- Any H controlled proof failure before terminal markers.
- Any H scoped health `FAIL`.
- Any SQL/CSV row or header mismatch for mapped rollback exports.

Phase status:
- code fix applied: yes - Batch 033 fixed `scripts/cycles/run_H_pricing_cycle.py` so H seller profile/SOI outputs and H listing offer history write through the SQL compatibility adapter.
- isolated verification passed: yes - final controlled H proof run `20260428T160125Z` finalized successfully with worker state `succeeded`, Sheet publish disabled, live price writes disabled, scheduler still disabled, and no owner processes or H locks remaining. Rollback validation passed `48/48`; H scoped health had `0 FAIL` and `4 WARN`.
- live loop verification: not yet proven. Scheduler ownership remains paused by design for this migration stage.

### Re-Enable Proof - A-Owned SQL-Primary Isolated Proof
Goal:
- Run the owned A cycle boundary under `sql_primary_csv_export` without Sheet writes or token mutation steps.

Allowed files for this phase:
- `scripts/cycles/run_A_all.py`
- `out/sql/sellerone_dev.sqlite3`
- A local output CSV compatibility exports.
- A manifests, A scoped health outputs, and rollback proof artifacts.
- `out/sql_migration/*`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- P002 forced proof output: `plans/active/sql-storage-migration-v1/forced_proof_A.json`
- A proof window status: `ready_now`.
- Use `run_A_all.bat` with SQL primary storage, Sheet writers disabled, stock receipts Sheet disabled, `A_EXTRA_SKIP_STEPS=A010_apply_researching_delta.py,A020_run_daily_finance.py`, and `A_B_RECOVERY_USE_SCHEDULER=0`.

Stop conditions:
- Any Sheet write attempt.
- Any token ledger row-count movement outside a planned token mutation proof.
- Any A cycle failure.
- Any A scoped health `FAIL`.
- Any SQL/CSV rollback export mismatch.

Phase status:
- code fix applied: yes - Batch 034 added `A_EXTRA_SKIP_STEPS` and B recovery disable support to the A runner for bounded isolated proof windows; the A wrapper now re-exports the real runner module for tests.
- isolated verification passed: yes - final A isolated proof run `20260428T163536Z` completed, A scoped health had `0 FAIL` and `0 WARN`, rollback validation passed `48/48`, token ledger/allocation row counts and hashes stayed stable, and no owner processes, A locks, B locks, or maintenance markers remained.
- dependency map: refreshed after A proof with `csv_dependency_remaining_count=0`, `registered_dependency_count=156`, `sql_primary_pilot_proven_count=164`, `unresolved_dynamic_count=800`, and `unregistered_csv_count=285`.
- live loop verification: not yet proven. Scheduler ownership remains paused by design for this migration stage.

### Live Restoration - Active Scheduler Ownership
Goal:
- Restore active scheduler ownership after isolated SQL-primary proof, using SQL-primary defaults in the active batch entrypoints.

Allowed files for this phase:
- `run_A_all.bat`
- `run_B_cycle.bat`
- `run_H_cycle.bat`
- `plans/active/sql-storage-migration-v1/*`
- Scheduler state for active A/B/H tasks.

Proof boundary:
- Enable only active non-reboot tasks: `AMZ Orders`, `AMZ H Cycle`, and `AMZ Pricing Summary`.
- Resume H controlled mode through H isolation tooling.
- Leave `AMZ Controlled Restart`, `AMZ Restart Postcheck`, and `AMZ Pricing Summary Hourly` disabled unless separately approved because they are reboot-capable or point at legacy `SELLER~1.0`.

Stop conditions:
- Duplicate owner process.
- A/B/H lock conflict.
- A restored task running from CSV mode.
- Rollback export mismatch after restoration.

Phase status:
- code fix applied: yes - Batch 035 set active A/B/H batch entrypoints to default `SELLERONE_STORAGE_MODE=sql_primary_csv_export` and `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`.
- live loop verification confirmed: yes - active non-reboot scheduler ownership was restored under SQL-primary defaults.
- B restored owner proof: `AMZ Orders` enabled and started B supervisor/cycle ownership. Restored B cycle `B_20260428T164227Z` finalized at `2026-04-28T16:56:29Z` with `final_state=completed`; the next restored cycle `B_20260428T165629Z` also finalized at `2026-04-28T17:00:43Z`, and B continued into another cycle. B split health stayed truthful with known `token_shortages_by_sku` FAIL and `order_master_placeholder_cogs_rows` WARN.
- H restored owner proof: H isolation resume cleared controlled mode and enabled `AMZ H Cycle`; first restored continuous run `20260428T164339Z` finalized, publish status was `ok`, `H_last_finalized_run_id.txt` became `20260428T164339Z`, and H immediately started next run `20260428T170156Z`.
- A restored scheduler proof: `AMZ Pricing Summary` is enabled with next run `29/04/2026 06:00:00` local time. No extra A run was forced after isolated proof to avoid duplicate daily ownership.
- intentionally disabled after restoration: `AMZ Controlled Restart`, `AMZ Restart Postcheck`, and `AMZ Pricing Summary Hourly` because they are reboot-capable, restart-controller, or legacy-path tasks.

### Follow-up - F/O New Product Review SQL Completion
Goal:
- Close the storage gap where New Product Review still reads and writes CSV review packs outside the registered SQL-primary migration scope.

Allowed files for this phase:
- `project_control/DATA_BLUEPRINT_REGISTRY.csv`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `scripts/core/storage/*`
- `scripts/one_off/F019_build_live_price_file_near_miss_pack.py`
- `scripts/flows/O/O400_operator_ui.py`
- selected F review automation one-offs that consume New Product Review packs
- targeted tests for F/O/storage
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- Current evidence shows F061 and O400 are active, so live seed/cutover must pause F/O ownership first.
- Keep CSV compatibility exports for operator download, fallback, and rollback.
- Do not touch Google Sheets, Product_DB authority, or F061 queue apply behavior.

Stop conditions:
- F061 or O400 cannot be paused cleanly before seed/cutover.
- New Product Review paths remain unregistered or unresolved after map repair.
- SQL/CSV row counts, headers, or event ids mismatch.
- O400 cannot load review rows from SQL-primary storage.

Phase status:
- study completed: yes - Batch 036 identified that `f_live_price_file_pass_review_*`, `f_live_price_file_near_miss_review_*`, `f_live_price_file_review_summary_*`, `feeder_review_events`, and `feeder_review_ui_drafts` were not in the original registered SQL migration scope.
- code fix applied: yes - Batch 036 registered the F/O datasets, added snapshot-aware review-pack SQL storage, converted F019/O400/F review consumers to SQL-first reads/writes, added O400 SQL defaults, and closed the newly exposed registered dependency gaps for A/H health and snapshot declarations.
- isolated verification passed: yes - py_compile passed for modified modules; targeted storage/F/O/P006/H/control tests passed `104 passed`, `1 warning`.
- live proof passed: yes for F/O New Product Review - backup created at `out/backups/sql_storage_migration_v1/batch_036_f_o_review_sql_20260429T150003Z`; F019 seeded SQL under `sql_primary_csv_export`; O400 SQL loader proof returned pass rows `3`, near-miss rows `1600`, events `13`, option count `29`; O400 restarted on port `8501` with PID `3064`.
- dependency map: refreshed after Batch 036 with `csv_dependency_remaining_count=0`, `registered_dependency_count=418`, `sql_primary_pilot_proven_count=447`, `unresolved_dynamic_count=790`, and `unregistered_csv_count=725`.
- residual test debt: `tests/test_a015_health_check_runtime.py` still has 5 unrelated behavioral failures; do not treat those as storage proof failures.

### Follow-up - B Finance And Order SQL Completion
Goal:
- Close the B finance/order CSV storage gap exposed after the O/F contract migration, while keeping CSV compatibility exports for rollback and older tooling.

Allowed files for this phase:
- `scripts/flows/B/_finance_io.py`
- `scripts/flows/B/B001_run_orders_to_sheet.py`
- `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
- `scripts/flows/B/B003_run_financial_events_level3.py`
- `scripts/flows/B/B004_build_order_master.py`
- `scripts/flows/B/B007_allocate_tokens_live.py`
- `scripts/flows/B/B024_build_tokens_november_anchor.py`
- `scripts/flows/B/B032_update_token_lot_rank_from_orders_sheet.py`
- `project_control/DATA_BLUEPRINT_REGISTRY.csv`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `tests/test_b_finance_io_sql.py`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- B maintenance requested at `2026-04-29T16:39:40Z`.
- B reported `maintenance.ready` at `2026-04-29T16:41:00Z`.
- SQLite backup created before live seed at `out/backups/sql_storage_migration_v1/batch_038_b_finance_20260429T165015Z`.
- Maintenance cleared only after code, seed, targeted tests, B-local proof, and dependency-map refresh.

Stop conditions:
- B maintenance handoff missing or stale.
- SQL seed row count mismatch for any non-empty seeded table.
- B-local Order Master proof fails.
- Targeted B/P006 tests fail.
- Live B cycle fails before finalization or B ownership does not continue.

Phase status:
- code fix applied: yes - Batch 038 added shared B finance SQL IO, converted B001/B002/B003/B004/B007/B024/B032 finance/order reads or writes to SQL-aware paths, registered the B finance/order datasets, and marked them as SQL-primary pilot proven in P006.
- isolated verification passed: yes - py_compile passed for modified modules; targeted tests passed `29 passed` via `python -m pytest tests/test_b_finance_io_sql.py tests/test_b003_run_financial_events_level3.py tests/test_b004_level_gate.py tests/test_b007_allocate_tokens_live.py tests/test_b008_apply_refunds_to_tokens.py tests/test_b_token_live_storage.py tests/test_p006_build_csv_dependency_map.py -q`.
- SQL seed passed: yes - `out/sql_migration/batch_038_b_finance_seed_summary.json` seeded 23 non-empty B finance/order tables with row-count matches; `out/order_items_raw.csv` was a zero-byte empty snapshot and therefore had no header/table to seed.
- B-local proof passed: yes - `B004_build_order_master.py` ran under `sql_primary_csv_export` with Sheet writes disabled and wrote `10250` Order Master rows.
- dependency map: refreshed after Batch 038 with `registered_dependency_count=508`, `sql_primary_pilot_proven_count=537`, `csv_dependency_remaining_count=0`, `unresolved_dynamic_count=710`, and `unregistered_csv_count=606`.
- live loop verification confirmed: yes - after maintenance clear, B finalized the paused cycle at `2026-04-29T16:55:55Z`, then the updated live B cycle `B_20260429T165555Z` finalized at `2026-04-29T17:07:20Z` with `final_state=completed`, `recorded_step_count=12`, `completed_step_count=12`, and B ownership continued with no maintenance markers left.
- residual B health state: known pre-existing `token_shortages_by_sku` FAIL and `order_master_placeholder_cogs_rows` WARN remain in `out/cycle_alerts/checklist_B_split.csv`; they are not storage migration failures.

### Follow-up - Product DB SQL Contract And Repricer Tracker UI Read Model
Goal:
- Define the target SQL Product DB table contract before Product DB writes move.
- Add a non-destructive staged legacy import check that fails closed on source schema defects.
- Add a read-only O UI repricer tracker backed by SQL/read-only H pricing outputs without changing `H130_build_phase1_observation_sheet.py`.

Allowed files for this phase:
- `scripts/core/storage/product_db_contract.py`
- `scripts/core/storage/__init__.py`
- `scripts/one_off/P008_product_db_sql_contract_check.py`
- `scripts/flows/O/O030_build_product_db_operator_view.py`
- `scripts/flows/O/O050_build_repricing_tracker_view.py`
- `scripts/flows/O/O450_repricing_tracker_ui.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/flows/O/_schemas.py`
- `scripts/cycles/run_O_cycle.py`
- targeted tests
- `project_control/TASK_QUEUE.md`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- No Google Sheets writes.
- No Product DB source mutation.
- No A, B, H, or scheduler changes.
- P008 may write only local validation artifacts under `out/sql_migration/product_db_contract/`.
- O030/O050 may write O-owned live read-model and health files under `out/systems/O/live/`.

Stop conditions:
- Product DB source duplicate headers, missing required columns, blank `seller_sku`, or duplicate `seller_sku` block staged import.
- Repricer tracker source missing required columns blocks clean tracker health.
- Blank `execution_write_status` remains a reported failure, not a normalized downstream status.
- Newer H runtime rows than the latest terminal marker are reported as a WARN so in-progress runtime evidence is not confused with finalized proof.

Phase status:
- code fix applied: yes - Batch 039 added the Product DB SQL contract helper, P008 local contract check, O Product DB source-health output, O repricer tracker read model, O400 `Repricer Tracker` page, and O runner integration.
- isolated verification passed: yes - focused Product DB/O tests passed: `20 passed` for `tests/test_product_db_sql_contract.py`, `tests/test_p008_product_db_sql_contract_check.py`, `tests/test_o030_build_product_db_operator_view.py`, `tests/test_o050_repricing_tracker_view.py`, `tests/test_o000_paths_and_schemas.py`, and `tests/test_o_cycle_runner.py`; wider O UI profile passed `76 passed`.
- local proof passed with expected blocks: P008 read `608` Product DB rows and `72` source columns, reported `1 FAIL`, `2 WARN`, `3 OK`, and skipped staged import because of duplicate source header `last_updated_A003`. Duplicate ASIN review report has `3` ASINs: `0786964502`, `B07RRQX71T`, and `B09NQ9ZHDQ`.
- O Product DB proof: `O030_build_product_db_operator_view` wrote `out/systems/O/live/product_db_operator_view.csv` with `608` rows and `out/systems/O/live/product_db_source_health.csv` with `1 FAIL`, `2 WARN`, `4 OK`.
- O repricer tracker proof: `O050_build_repricing_tracker_view` wrote `out/systems/O/live/repricer_tracker_view.csv` with `89` rows and `out/systems/O/live/repricer_tracker_health.csv`. Health reports `2 FAIL` for `20` blank `execution_write_status` rows in both runtime and compact pricing outputs, plus `2 WARN` for newer runtime run `20260501T143621Z` versus terminal run `20260501T142053Z` and terminal rows `26` versus publish rows `49`.
- live loop verification: not applicable - this was a local O read-model and validation batch. No A/B/H owner proof was run and no scheduler ownership was changed.

### Follow-up - Product DB Scanner Link Simulation
Goal:
- Add a local-only scanner to Product DB link simulator that can classify rows as `WOULD INSERT`, `WOULD UPDATE`, `REVIEW`, or `BLOCKED`.
- Keep scanner same-ASIN/different-supplier rows visible for review while collapsing only exact `asin + supplier_sku` duplicates.
- Fail closed when Product DB schema validation fails.

Allowed files for this phase:
- `scripts/one_off/P009_product_db_link_simulation.py`
- `tests/test_p009_product_db_link_simulation.py`
- `project_control/TASK_QUEUE.md`
- `project_control/PRODUCT_DB_CONTRACT.md`
- `project_control/CURRENT_STATE.md`
- `project_control/SCRIPT_INVENTORY.csv`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- No Google Sheets writes.
- No SQL writes.
- No CSV output writes.
- No Product DB source mutation.
- No A, B, H, or scheduler changes.

Stop conditions:
- Product DB schema validation fails, in which case simulated row actions must be `BLOCKED`.
- Scanner required columns `asin` or `supplier_sku` are missing.
- Tests fail for insert/update/review/block behavior.

Phase status:
- code fix applied: yes - Batch 040 added `scripts/one_off/P009_product_db_link_simulation.py` and `tests/test_p009_product_db_link_simulation.py`.
- isolated verification passed: yes - `python -m pytest tests/test_p009_product_db_link_simulation.py tests/test_product_db_sql_contract.py tests/test_p008_product_db_sql_contract_check.py -q` passed `9` tests; `python -m py_compile scripts\one_off\P009_product_db_link_simulation.py tests\test_p009_product_db_link_simulation.py` passed.
- local proof passed with expected block: `python -m scripts.one_off.P009_product_db_link_simulation --sample-size 3` returned exit code `1` by design because the live Product DB contract is failed. It read `51` scanner rows and `608` Product DB rows, produced `51` simulation rows, and action counts were `{"BLOCKED": 51}` with block reason `product_db_schema_failed:product_db_unique_headers`.
- scanner duplicate proof: current duplicate scanner ASIN rows are `B0DPMGDZLZ / 1320217` and `B0DPMGDZLZ / 1320221`; they remain visible for review.
- live loop verification: not applicable - this was a read-only local simulation. No A/B/H owner proof was run and no scheduler ownership was changed.

### Follow-up - Product DB Duplicate Header Source/Export Repair
Goal:
- Fix duplicate Product_DB header `last_updated_A003` at the source/export generation path.
- Keep Product DB export rows and Sheet update rows schema-unique before writing.
- Preserve existing duplicate-column data by keeping the rightmost canonical header and filling blanks from earlier duplicates before removing earlier duplicate columns.

Allowed files for this phase:
- `scripts/core/storage/product_db_contract.py`
- `scripts/core/storage/__init__.py`
- A/B Product DB preview/export touchpoints:
  - `scripts/flows/A/A001_run_listings_to_sheet.py`
  - `scripts/flows/A/A002_run_catalog_items_to_sheet.py`
  - `scripts/flows/A/A003_run_inventory_to_sheet.py`
  - `scripts/flows/A/A004_run_fees_to_sheet.py`
  - `scripts/flows/B/B001_run_orders_to_sheet.py`
  - `scripts/flows/B/B002_run_pending_orders_to_sheet.py`
  - `scripts/flows/B/B003_run_financial_events_level3.py`
- targeted tests and control files

Proof boundary:
- Google Sheets were not changed during this proof.
- No A cycle, B cycle, H cycle, or scheduler run was started.
- Current local `out/product_db_preview.csv` was repaired using the same approved export helper so local contract proof could run.

Stop conditions:
- Product DB contract still reports duplicate headers.
- Staged SQL import fails.
- P009 link simulation still reports schema-driven `BLOCKED`.
- Touched A/B modules fail compile.

Phase status:
- code fix applied: yes - Batch 041 added shared duplicate-header coalescing helpers and wired them into A/B Product DB update/export paths.
- isolated verification passed: yes - `python -m py_compile` passed for the touched storage helper and A/B Product DB exporter modules. `python -m pytest tests/test_product_db_sql_contract.py tests/test_product_db_preview_storage.py tests/test_p008_product_db_sql_contract_check.py tests/test_p009_product_db_link_simulation.py -q` passed `12` tests.
- local preview repair passed: current `out/product_db_preview.csv` stayed at `608` rows, changed from `72` columns to `71`, and has no duplicate headers.
- local Product DB SQL proof passed with warnings: P008 reported `0 FAIL`, `2 WARN`, `4 OK`, staged import `passed`, rows `608`, unique `seller_sku` `608`.
- local scanner link proof passed with warnings: P009 reported action counts `{"REVIEW": 2, "WOULD INSERT": 49}` and no schema-driven `BLOCKED` rows.
- O Product DB source health proof passed with warnings: O030 wrote `608` operator rows and source health has `5 OK`, `2 WARN`, `0 FAIL`.
- remaining WARNs: duplicate Product DB ASINs `0786964502`, `B07RRQX71T`, `B09NQ9ZHDQ`; blank ASIN rows `289`; scanner duplicate ASIN `B0DPMGDZLZ`.
- live loop verification: not applicable - no A/B/H owner proof was run and no scheduler ownership was changed.

### Follow-up - Product DB Review Pack
Goal:
- Build local review artifacts for Product DB duplicate ASIN classifications and scanner link candidates.
- Keep suggested classifications non-authoritative until business review chooses a reason or cleanup action.
- Preserve all scanner `WOULD INSERT` and `REVIEW` rows for operator inspection before any real Product DB insert or update path exists.

Allowed files for this phase:
- `scripts/one_off/P010_product_db_review_pack.py`
- `tests/test_p010_product_db_review_pack.py`
- `project_control/TASK_QUEUE.md`
- `project_control/PRODUCT_DB_CONTRACT.md`
- `project_control/CURRENT_STATE.md`
- `project_control/DATA_BLUEPRINT_REGISTRY.csv`
- `project_control/SCRIPT_INVENTORY.csv`
- `plans/active/sql-storage-migration-v1/*`

Proof boundary:
- No Google Sheets writes.
- No SQL writes.
- No Product DB source mutation.
- No A, B, H, or scheduler changes.
- P010 writes only local review artifacts under `out/sql_migration/product_db_contract/`.

Stop conditions:
- Product DB contract is failed.
- P009 link simulation returns schema-driven `BLOCKED`.
- Review output schemas do not match expected columns.
- Targeted tests fail.

Phase status:
- code fix applied: yes - Batch 042 added `scripts/one_off/P010_product_db_review_pack.py` and `tests/test_p010_product_db_review_pack.py`.
- isolated verification passed: yes - `python -m py_compile scripts\one_off\P010_product_db_review_pack.py tests\test_p010_product_db_review_pack.py` passed; `python -m pytest tests/test_p010_product_db_review_pack.py tests/test_p009_product_db_link_simulation.py tests/test_product_db_sql_contract.py -q` passed `11` tests.
- local review proof passed with warnings: `python -m scripts.one_off.P010_product_db_review_pack --format json` returned status `warn`, Product DB rows `608`, scanner rows `51`, duplicate ASIN review rows `3`, scanner link review rows `51`.
- duplicate ASIN suggestions: `2` `legacy_or_replacement_listing_candidate`, `1` `inactive_duplicate_candidate`; all have `classification_status=needs_user_decision`.
- scanner link review: `49` `WOULD INSERT`, `2` `REVIEW`, and `0` `BLOCKED`.
- local outputs:
  - `out/sql_migration/product_db_contract/product_db_duplicate_asin_classification_review.csv`
  - `out/sql_migration/product_db_contract/scanner_product_db_link_review.csv`
  - `out/sql_migration/product_db_contract/product_db_review_pack_summary.json`
- live loop verification: not applicable - this was a read-only local review-pack batch.

### Follow-up - Scanner Product DB SQL Inserts
Goal:
- Apply the user-approved scanner new-product inserts without building another UI page.
- Use existing `NP-{supplier-code}-{HASH8}` seller SKU convention rather than raw supplier SKU.
- Record same-ASIN/different-SKU rows as separate products with reason `different_sku_separate_product_not_sold_together`.
- Write SQL Product DB first and refresh the local CSV mirror after SQL write.

Allowed files for this phase:
- `scripts/one_off/P011_apply_scanner_product_db_inserts.py`
- `tests/test_p011_apply_scanner_product_db_inserts.py`
- `scripts/core/storage/product_db_contract.py`
- `scripts/one_off/P010_product_db_review_pack.py`
- control/registry files
- local SQL DB and local Product DB mirror outputs

Proof boundary:
- No Google Sheets writes.
- No A, B, H, or scheduler runs.
- SQL write limited to `out/sql/sellerone_dev.sqlite3:product_db_products`.
- CSV mirror refresh limited to `out/product_db_preview.csv` after SQL write.

Stop conditions:
- Product DB contract has any FAIL.
- Generated `seller_sku` collision.
- SQL row count and unique seller SKU count mismatch.
- Tests fail.

Phase status:
- code fix applied: yes - Batch 043 added P011, tests, duplicate-ASIN reason-aware validation, and review-pack classification handling.
- isolated verification passed: yes - `python -m py_compile scripts\one_off\P011_apply_scanner_product_db_inserts.py tests\test_p011_apply_scanner_product_db_inserts.py` passed; `python -m pytest tests/test_p011_apply_scanner_product_db_inserts.py tests/test_p010_product_db_review_pack.py tests/test_p009_product_db_link_simulation.py tests/test_product_db_sql_contract.py -q` passed `14` tests.
- local SQL insert proof passed: P011 applied 51 scanner inserts, held rows `0`, final Product DB rows `659`, SQL rows `659`, SQL unique seller SKU `659`, duplicate-ASIN reason rows `9`.
- local Product DB mirror proof passed: `out/product_db_preview.csv` has 659 rows and 79 columns, including duplicate-ASIN reason and scanner trace fields.
- contract proof passed with warning only: P008 reports `0 FAIL`, `1 WARN`, `5 OK`, staged import `passed`, rows `659`, unique `seller_sku` `659`, duplicate-ASIN review count `0`.
- O Product DB source health proof passed with warning only: O030 wrote 659 operator rows.
- remaining WARN: Product DB blank ASIN rows still exist from older source rows.
- live loop verification: not applicable - no A/B/H owner proof was run and no scheduler ownership was changed.

### Follow-up - Scanner Identity Uniqueness Proof
Goal:
- Add a durable local proof that scanner identity is unique by `asin + supplier_sku`.
- Treat same-ASIN/different-supplier-SKU rows as separate product context, not exact duplicates.
- Keep the proof independent of live scanner ownership and Product DB writes.

Allowed files for this phase:
- `scripts/one_off/P012_scanner_identity_check.py`
- `tests/test_p012_scanner_identity_check.py`
- control/registry files
- local proof outputs under `out/sql_migration/product_db_contract/`

Proof boundary:
- No Google Sheets writes.
- No SQL writes.
- No Product DB source mutation.
- No A, B, H, or scheduler runs.

Stop conditions:
- Scanner source missing required identity columns.
- Exact duplicate `asin + supplier_sku` keys exist.
- Tests fail.

Phase status:
- code fix applied: yes - Batch 044 added P012 scanner identity proof and tests.
- isolated verification passed: yes - `python -m py_compile scripts\one_off\P012_scanner_identity_check.py tests\test_p012_scanner_identity_check.py` passed; `python -m pytest tests/test_p012_scanner_identity_check.py tests/test_p009_product_db_link_simulation.py tests/test_p010_product_db_review_pack.py tests/test_p011_apply_scanner_product_db_inserts.py -q` passed `12` tests.
- local proof passed: `python -m scripts.one_off.P012_scanner_identity_check --format json` reported status `ok`, scanner rows `51`, unique `asin + supplier_sku` keys `51`, exact duplicate key count `0`, same-ASIN/different-supplier-SKU count `1`, blank ASIN rows `0`, and missing supplier SKU rows `0`.
- local outputs:
  - `out/sql_migration/product_db_contract/scanner_identity_check.csv`
  - `out/sql_migration/product_db_contract/scanner_same_asin_context.csv`
  - `out/sql_migration/product_db_contract/scanner_identity_check_summary.json`
- live loop verification: not applicable - no F/A/B/H owner proof was run and no scheduler ownership was changed.

### Follow-up - Repricer Write-Status Proof Summary
Goal:
- Investigate blank `execution_write_status` rows without masking them downstream.
- Add a compact read-only proof summary with latest H terminal run id, terminal state, publish status, publish rows, and write-status counts.
- Classify blank-status rows by source evidence so the next H fix can target the earliest correct stage.

Allowed files for this phase:
- `scripts/one_off/P013_repricing_write_status_proof.py`
- `tests/test_p013_repricing_write_status_proof.py`
- control/registry files
- local proof outputs under `out/sql_migration/product_db_contract/`

Proof boundary:
- No Google Sheets writes.
- No H cycle code changes.
- No A, B, H, or scheduler runs.
- Read only `out/phase1_runtime_floor_snapshot_latest.csv`, `out/pricing_output.csv`, and H terminal/publish marker files.

Stop conditions:
- Unknown blank write-status root cause remains.
- A non-contract write status appears.
- Tests fail.

Phase status:
- code fix applied: yes - Batch 045 added P013 read-only repricer write-status proof and tests.
- isolated verification passed: yes - `python -m py_compile scripts\one_off\P013_repricing_write_status_proof.py tests\test_p013_repricing_write_status_proof.py` passed; `python -m pytest tests/test_p013_repricing_write_status_proof.py tests/test_o050_repricing_tracker_view.py -q` passed `5` tests.
- local proof completed with warning: `python -m scripts.one_off.P013_repricing_write_status_proof --format json` reported terminal run `20260501T153744Z`, terminal state `finalized`, publish status `ok`, publish rows `49`, runtime rows `89`, pricing rows `89`, runtime blank write-status rows `20`, pricing blank write-status rows `20`, invalid write-status rows `0`, and unknown blank root-cause rows `0`.
- blank-status root-cause split: pricing output has `17` `no_market_data_execution_context_cleared` rows and `3` `parked_execution_context_cleared` rows; runtime floor snapshot has `17` `no_market_data_execution_context_cleared` rows and `3` `parked_execution_context_cleared` rows.
- contract decision: user approved accepting `WRITE_NOT_APPLIED` as a valid write-status value because it is already produced by the write-verification path when a write was attempted but not applied.
- local outputs:
  - `out/sql_migration/product_db_contract/repricing_write_status_root_cause.csv`
  - `out/sql_migration/product_db_contract/repricing_write_status_proof_summary.json`
- live loop verification: not applicable - no H owner proof was run and no scheduler ownership was changed.

### Follow-up - WRITE_NOT_APPLIED Contract Acceptance
Goal:
- Accept `WRITE_NOT_APPLIED` as a valid repricer write-status value in read-only O/P013 proof surfaces.
- Do not change H runtime behavior or scheduler ownership in hometime mode.
- Keep blank `execution_write_status` rows visible as the remaining source defect.

Allowed files for this phase:
- `scripts/flows/O/O050_build_repricing_tracker_view.py`
- `scripts/one_off/P013_repricing_write_status_proof.py`
- `tests/test_p013_repricing_write_status_proof.py`
- control/plan files

Proof boundary:
- No Google Sheets writes.
- No H cycle code changes.
- No A, B, H, or scheduler runs started by Codex.
- O050 may rebuild the local O read model from read-only H outputs.

Stop conditions:
- Nonblank repricer write statuses still fail contract validation.
- Blank write-status rows are hidden or normalized downstream.
- Tests fail.

Phase status:
- code fix applied: yes - Batch 046 added `WRITE_NOT_APPLIED` to O050/P013 allowed status lists and recorded the contract decision.
- isolated verification passed: yes - `python -m pytest tests/test_p013_repricing_write_status_proof.py tests/test_o050_repricing_tracker_view.py -q` passed `5` tests.
- local proof passed with warning: P013 now reports `invalid_execution_write_status_rows=0`, `unknown_blank_root_cause_rows=0`, and `status=warn` because 20 blank H source rows remain.
- local O read-model proof passed with source failures still visible: O050 rebuilt 89 repricer tracker rows; health reports invalid status `ok`, terminal rows `49/49` `ok`, and blank status failures remain at 20 runtime rows plus 20 compact pricing rows.
- next source fix for tomorrow: in H-owned source generation, set `execution_write_status=READ_ONLY_NO_WRITE` for current-cycle no-market-data rows and `execution_write_status=NO_WRITE_REQUIRED` for parked rows when stale execution context is cleared, while keeping stale columns for audit.
- live loop verification: not applicable - no H owner proof was run and no scheduler ownership was changed.

### Follow-up - H Source Blank Write-Status Normalization
Goal:
- Fix blank `execution_write_status` at the H source instead of masking it in O.
- Preserve stale execution audit columns when stale execution context is cleared.
- Keep no-market-data rows and parked rows explicit as no-write outcomes.

Allowed files for this phase:
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/flows/H/H130_build_phase1_observation_sheet.py`
- `scripts/one_off/P013_repricing_write_status_proof.py`
- `scripts/flows/O/O050_build_repricing_tracker_view.py`
- `tests/test_h_split_health_gate.py`
- `tests/test_p013_repricing_write_status_proof.py`
- `tests/test_o050_repricing_tracker_view.py`
- control/plan files

Proof boundary:
- Google Sheets must not be changed during isolated proof.
- Do not run H through scheduler implicitly.
- Live sign-off requires an H-owned proof window: pause scheduler ownership if needed, run the guarded H controlled one-shot, run P013/O050 after finalization, then confirm ownership restoration.

Stop conditions:
- Blank write-status rows remain after an H-owned proof run.
- Latest H terminal run is failed or did not publish.
- Stale execution audit columns are lost.
- Targeted H/O/P013 tests fail.

Phase status:
- code fix applied: yes - 2026-05-01T17:55Z - `run_H_pricing_cycle.py` sets and re-asserts `READ_ONLY_NO_WRITE` for current-cycle no-market-data rows after stale execution context is cleared and truth reconciliation; parked rows emit `NO_WRITE_REQUIRED`; `H130_build_phase1_observation_sheet.py` sets parked rows to `NO_WRITE_REQUIRED`.
- proof handling applied: yes - 2026-05-01T17:58Z - P013/O050 now mark stale audit `out/pricing_output.csv` separately when it is older than runtime and missing latest runtime-backed run rows.
- isolated verification passed: yes - `python -m py_compile scripts\cycles\run_H_pricing_cycle.py scripts\flows\O\O050_build_repricing_tracker_view.py scripts\one_off\P013_repricing_write_status_proof.py tests\test_h_split_health_gate.py tests\test_p013_repricing_write_status_proof.py tests\test_o050_repricing_tracker_view.py` passed; `python -m pytest tests/test_h_split_health_gate.py tests/test_p013_repricing_write_status_proof.py tests/test_o050_repricing_tracker_view.py tests/test_p012_scanner_identity_check.py tests/test_p011_apply_scanner_product_db_inserts.py -q` passed `25` tests with 1 deprecation warning and the known Windows pytest temp cleanup PermissionError after exit.
- item_offers timeout root fix applied: yes - 2026-05-01T18:08Z - `_run_item_offers_lookup_guarded` now receives the remaining retry-aware snapshot budget instead of always using the fixed 240-second item-offers watchdog. This keeps one-cycle retry sweeps from being killed before the approved snapshot budget is spent.
- timeout isolated verification passed: yes - `python -m py_compile scripts\cycles\run_H_pricing_cycle.py tests\test_h_item_offers_retry_queue.py` passed; `python -m pytest tests/test_h_item_offers_retry_queue.py tests/test_h_split_health_gate.py tests/test_p013_repricing_write_status_proof.py tests/test_o050_repricing_tracker_view.py -q` passed `41` tests with 1 deprecation warning and the known Windows pytest temp cleanup PermissionError after exit.
- local proof after failed H run: P013 at 2026-05-01T17:58:33Z reports `status=fail`, `terminal_run_id=20260501T174941Z`, `terminal_state=failed`, `terminal_blocker_reason=terminal_state_not_finalized`, `latest_runtime_run_id=20260501T173839Z`, `runtime_blank_execution_write_status_rows=9`, `invalid_execution_write_status_rows=0`, `unknown_blank_root_cause_rows=0`, and `pricing_output_stale=true`.
- O read-model proof after failed H run: O050 rebuilt 89 tracker rows; health correctly shows runtime blank status `fail=9`, latest terminal state `fail=failed`, stale compact pricing output `warn=20`, and invalid status `ok=0`.
- live loop verification confirmed: owner run `20260501T183549Z` loaded both the blank-status fix and the item-offers timeout-budget fix, finalized at `2026-05-01T18:56:08Z`, and published with status `ok`.
- item-offers live proof confirmed: run `20260501T183549Z` logged `snapshot_refresh item_offers watchdog_budget_override base_seconds=240 effective_seconds=609 snapshot_budget_seconds=645` and completed item-offers in `190.70` seconds.
- P013 live proof confirmed with stale-audit warning only: at `2026-05-01T18:56:55Z`, P013 reported `terminal_run_id=20260501T183549Z`, `terminal_state=finalized`, `terminal_publish_status=ok`, `publish_rows=49`, `runtime_proof_run_rows=49`, `runtime_blank_execution_write_status_rows=0`, `runtime_invalid_execution_write_status_rows=0`, `unknown_blank_root_cause_rows=0`, and proof-run status counts `APPLIED=3`, `NO_WRITE_REQUIRED=34`, `READ_ONLY_NO_WRITE=12`.
- O050 read-model proof confirmed with stale-audit warning only: O050 rebuilt `89` tracker rows; `repricer_tracker_health.csv` has runtime blank status `ok`, invalid status `ok`, latest terminal state `ok`, latest terminal rows `ok=49`, publish marker `ok=49`, terminal rows versus publish rows `ok=49/49`, and two warnings only for stale `out/pricing_output.csv`.
- failed prior terminal understood: run `20260501T181911Z` failed closed in `startup_reconcile` with `STALE_OWNER_IDENTITY_MISMATCH` after its owner PID died during `phase1_pilot`; the next owner run `20260501T183549Z` completed cleanly, so this did not block tracker read-model sign-off.

### Follow-up - Product DB SQL And Repricer Tracker UI Completion Block
Goal:
- Work through the user-approved 1-7 completion plan in home time mode.
- Keep the Product DB migration SQL-first and UI-edited.
- Keep the repricer tracker UI backed by read-only runtime/proof outputs.
- Do not change Google Sheets, A cycle, B cycle, H cycle, or scheduler during this block.

Allowed files and artifacts for this block:
- `scripts/core/storage/*`
- `scripts/flows/O/*`
- `scripts/one_off/P008_product_db_sql_contract_check.py` through `P013_repricing_write_status_proof.py`
- new local-only proof/check scripts under `scripts/one_off/`
- targeted tests under `tests/`
- local proof outputs under `out/sql_migration/product_db_contract/` and O-owned local outputs under `out/systems/O/`
- control files under `project_control/` and this plan folder

Blocked without a separate explicit approval:
- Google Sheets writes
- A-owned runtime or A015 runs
- B-owned runtime or maintenance proof runs
- H-owned runtime or scheduler proof runs
- scheduler task changes
- production PostgreSQL promotion that needs external credentials or live production DB access

Phase 1 - Refresh local proof and evidence drift:
- Rebuild Product DB contract proof, scanner identity proof, O Product DB operator view, P013 repricer proof, and O050 tracker read model from existing local artifacts.
- Success: Product DB SQL/local mirror/O view agree on row count and unique `seller_sku`; tracker health has no current runtime blank/invalid write-status rows.

Phase 2 - Finish Product DB UI write path locally:
- Verify or add local-only Product DB edit event apply proof for staged UI events.
- Success: edit events validate identity, reject unsafe duplicate `seller_sku`, apply only to local SQL/mirror in tests, and never touch Google Sheets.

Phase 3 - Product DB cutover rehearsal:
- Add a read-only/local rehearsal proof that SQL can be treated as Product DB authority while CSV remains export/mirror.
- Success: SQL authority rows reconcile to mirror rows and direct legacy CSV authority is not required for the O Product DB proof.

Phase 4 - Repricer tracker UI cutover proof:
- Confirm O050/O450/O400 are enough for an operator-facing UI tracker while the Google Sheet remains temporary/fallback.
- Success: tracker read model and health proof pass current runtime gates; control docs state the Sheet is fallback until explicit cutover.

Phase 5 - Stale pricing audit cleanup:
- Keep stale `out/pricing_output.csv` visible as audit-only, or refresh/archive it only through a proper local export path.
- Success: proof says current tracker surfaces use latest H runtime/read-model data, not stale compact pricing output.

Phase 6 - Flow-by-flow expansion preparation:
- Prepare the O/F/E/B/A/H expansion sequence and proof gates without changing A/B/H runtime ownership.
- Success: task queue and plan name the exact flow-owned proof windows and blockers.

Phase 7 - PostgreSQL promotion preparation:
- Prepare the production PostgreSQL promotion checklist and tests using local/optional-driver proof only.
- Success: production promotion remains planned and gated by credentials, backup, rollback, and explicit cutover approval.

Phase status:
- Phase 1 refreshed local proof: completed - P011 restored SQL to 659 rows and 659 unique `seller_sku`; P008 then reported 659 source rows, 0 FAIL, 1 WARN; O030 rebuilt 659 rows; P013/O050 were rerun from existing H artifacts.
- Phase 2 local Product DB edit path: completed - added `P014_apply_product_db_edit_events.py`; tests passed; real dry-run loaded SQL authority with 659 rows, SQL alignment ok, and 0 pending event rows.
- Phase 3 SQL authority rehearsal: completed with warning - O030 now prefers SQL Product DB authority when `product_db_products` exists; P015 reported SQL 659 rows, O view 659 rows, CSV mirror 608 rows, 0 FAIL, 3 WARN.
- Phase 4 repricer tracker UI cutover proof: completed with stale-audit warning - latest checked H run `20260501T203514Z` finalized with publish status `ok`; P013 at `2026-05-01T21:01:39Z` reported runtime blank write-status rows `0`, invalid write-status rows `0`, terminal publish `ok`, and stale compact `out/pricing_output.csv` as audit-only. O050 now compares publish marker rows to the filtered H130 dashboard view rows, not raw runtime processed SKU rows. P016 at `2026-05-01T21:01:46Z` returned `ready_with_stale_audit_warning`, `fail_count=0`, `warn_count=1`, tracker rows `89`, and Sheet status `temporary_fallback_until_explicit_operator_cutover`.
- Phase 5 stale pricing audit behavior: completed for classification - P013/O050/P016 keep stale `out/pricing_output.csv` visible as stale audit warning; no downstream blank-status masking was added.
- Phase 6 flow expansion preparation: completed - `FLOW_EXPANSION_GATES.md` records O/F/E/B/A/H gates and current blockers without changing A/B/H/scheduler.
- Phase 7 PostgreSQL promotion preparation: completed - `POSTGRES_PROMOTION_CHECKLIST.md` records preconditions, tests, rollback, and explicit approval gates. No PostgreSQL promotion was run.
- isolated verification: passed - focused pytest profiles for P014/P015/O030/Product DB and P016/P013/O050 passed; latest check passed `24` focused tests for Product DB/O/repricer proof.
- live loop verification: tracker read-model proof confirmed against terminal H run `20260501T203514Z`. A transient H staged-publish `PermissionError` was observed on run `20260501T193132Z`; later finalized H evidence did not show recurrence, but due register still tracks fresh-owner live-load proof because the observed owner PID was already running before the patch.
- next phase pointer: `plans/active/sql-product-db-ui-authority-phase2-2026-05-01/CODING_PLAN.md`.

## 3) Global Completion Rule
- A phase is not complete until the phase status line is updated with factual proof.
- Do not use `monitor and wait` as the final state.
- Do not use `wait for the next scheduled cycle` as the default when a forced proof window exists.
- If the monitoring window expires, record the exact parked condition and exact resume trigger.
- Passive monitoring should stay silent unless the interruption threshold is met.
- The migration is not complete until rollback has been tested and remaining CSV exports are explicitly documented.
