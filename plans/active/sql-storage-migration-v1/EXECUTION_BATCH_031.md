# Execution Batch 031 - B-Owned SQL-Primary Local Proof

Started UTC: 2026-04-28T14:51:37Z
Completed UTC: 2026-04-28T14:54:51Z
Status: completed - local SQL-primary proof passed; full live B loop not yet proven

## Purpose
- Run the first B proof after rollback validation while schedulers remain disabled.
- Keep proof local: no SP-API calls and no Google Sheets writes.
- Validate SQL-primary writes continue to emit compatible CSV exports.

## Preflight Evidence
- No active `python.exe` process was visible.
- AMZ scheduled tasks remained disabled.
- B lock markers were absent:
  - `out/systems/B/live/B_cycle.lock`
  - `out/B_cycle.lock`
  - `out/locks/maintenance.requested`
  - `out/locks/maintenance.ready`
  - `out/locks/maintenance.active`
  - `out/locks/b_cycle.maintenance`
- P002 forced proof planner was run for B and wrote `forced_proof_B.json`.

## Full B_RUN_ONCE Scope Decision
- Full B runner ownership is boundary-ready, but it is not local-safe.
- Current full runner can call:
  - B001 live order SP-API
  - B002 pending-order SP-API
  - listing/refund API collections
  - B011 orphan recovery SP-API when `out/l3_orphans.csv` has rows
  - quiet-mode Sheet publish for Order Master and P&L
- Therefore Batch 031 uses local B-owned proof steps first.

## Planned Local Proof Steps
- `B030_sync_token_allocations_from_sheet.py`
- `B025_build_token_cogs_ledger.py`
- `B004_build_order_master.py` with `ORDER_MASTER_SKIP_SHEETS=1`
- `B006_build_fx_ledgers.py`
- rollback export validation for B SQL/CSV parity

Skipped by design:
- `B007_allocate_tokens_live.py` was not run because it can mutate token allocation state. Token row counts and hashes were checked before and after instead.

## Results
- Environment:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
  - `B_CYCLE_QUIET=1`
  - `ORDER_MASTER_SKIP_SHEETS=1`
  - `TOKEN_SKIP_SHEET_READS=1`
  - `FX_STALE_DAYS=999999`
- Local steps passed:
  - `B030_sync_token_allocations_from_sheet.py`: `11813` rows
  - `B025_build_token_cogs_ledger.py`: `11817` rows, SQL table `b_token_cogs_ledger`
  - `B004_build_order_master.py`: `10183` rows, `write_sheets=False`
  - `B006_build_fx_ledgers.py`: completed
- Token stability:
  - `out/token_ledger_live.csv`: `13594` rows before and after; hash unchanged.
  - `out/systems/B/live/token_ledger_live.csv`: `13594` rows before and after; hash unchanged.
  - `out/token_allocations_live.csv`: `11813` rows before and after; hash unchanged.
  - `out/systems/B/live/token_allocations_live.csv`: `11813` rows before and after; hash unchanged.
- B output row counts:
  - `out/token_cogs_ledger.csv`: `11817` rows before and after; regenerated hash changed.
  - `out/order_master.csv`: `10183` rows before and after; regenerated hash changed.
  - `out/order_ledger_fx.csv`: `10183` rows before and after; regenerated hash changed.
  - `out/financial_ledger_fx.csv`: `177007` rows before and after; hash unchanged.
  - `out/fx_rates_daily.csv`: `1100` rows before and after; hash unchanged.
- SQL row counts after proof:
  - `b_token_allocations_live`: `11813`
  - `b_token_cogs_ledger`: `11817`
  - `b_order_master`: `10183`
  - `b_order_ledger_fx`: `10183`
  - `b_financial_ledger_fx`: `177007`
  - `b_fx_rates_daily`: `1100`
- Rollback validation:
  - `status=passed`
  - `checked_count=48`
  - `pass_count=48`
  - `fail_count=0`
  - `missing_csv_count=0`
  - `missing_table_count=0`
  - export bundle: `out/sql_migration/rollback_exports_20260428T145419Z`
- Ownership after proof:
  - AMZ scheduled tasks remained disabled.
  - No Python owner process remained.
  - No B lock or maintenance marker was present.

## Remaining Proof Gap
- Full B loop verification is not yet proven.
- Reason: the full runner can call live SP-API paths and Sheet publish paths. It should not be run as the next proof unless that live scope is explicitly approved or the runner gets a dedicated no-API/no-Sheets proof mode.
