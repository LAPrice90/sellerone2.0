# Execution Batch 018 - B006 FX Ledgers SQL Expansion

Date: 2026-04-28
Status: local runtime verification passed

## Goal
- Expand B-flow SQL-primary coverage to B006 FX-normalized ledgers and the FX-rate cache.

## Scope
- Registered datasets:
  - `B.ORDER_LEDGER_FX`
  - `B.FINANCIAL_LEDGER_FX`
  - `B.FX_RATES_DAILY`
- Compatibility CSV exports:
  - `out/order_ledger_fx.csv`
  - `out/financial_ledger_fx.csv`
  - `out/fx_rates_daily.csv`
- SQL tables:
  - `b_order_ledger_fx`
  - `b_financial_ledger_fx`
  - `b_fx_rates_daily`

## Allowed Changes
- `scripts/flows/B/B006_build_fx_ledgers.py`
- `tests/test_b006_build_fx_ledgers.py`
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- Runtime proof must not require an external FX API call.
- Existing local FX cache must cover all current date/currency pairs before proof.

## Verification
- Preflight:
  - Current local data required AED, EUR, GBP, and SAR rates.
  - `out/fx_rates_daily.csv` had `1100` rows and no missing current date/currency pairs after stale filtering.
- Focused isolated command:
  - `PYTHONPATH=<repo_root> pytest tests/test_b006_build_fx_ledgers.py tests/test_storage_adapter.py`
- Local runtime proof:
  - `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
  - `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
  - `python scripts/flows/B/B006_build_fx_ledgers.py`
- Broad migration regression:
  - `PYTHONPATH=<repo_root> pytest tests/test_storage_adapter.py tests/test_b006_build_fx_ledgers.py tests/test_b004_level_gate.py tests/test_b012_build_token_events_append.py tests/test_b025_build_token_cogs_ledger.py tests/test_b010_build_token_ops_outputs.py tests/test_b014_build_token_daily_checklist.py tests/test_a006_build_stock_events_raw.py tests/test_e001_build_sales_velocity.py tests/test_e002_build_roi_snapshot.py tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_e006_build_sales_truth_reconciliation.py tests/test_e007_build_sku_daily_sales_truth.py tests/test_h004_build_daily_market_snapshot.py`

## Result
- Code fix applied: yes - B006 now writes `b_order_ledger_fx`, `b_financial_ledger_fx`, and `b_fx_rates_daily` in SQL-primary mode while retaining CSV compatibility exports.
- Isolated verification passed: yes - focused B006/storage tests passed 9 tests using fixture FX cache data.
- Local runtime verification passed: yes - B006 ran with SQL-primary mode using the current local FX cache.
- Row-count proof: `b_order_ledger_fx` `10183` matched `out/order_ledger_fx.csv` `10183`; `b_financial_ledger_fx` `177007` matched `out/financial_ledger_fx.csv` `177007`; `b_fx_rates_daily` `1100` matched `out/fx_rates_daily.csv` `1100`.
- Broad migration regression passed: yes - broad SQL migration regression passed 50 tests with `PYTHONPATH` set to the repo root.
- Full B-cycle proof not run for this batch: the direct B006 run proved the local transform outputs without widening into B cycle API/Sheet-capable steps.
- Dependency map: regenerated `out/sql_migration/csv_dependency_map.csv`; summary shows `1274` CSV calls, `191` registered dependencies, `81` SQL-primary pilot-proven calls, `118` remaining registered CSV dependencies, `795` unresolved dynamic calls, and `288` unregistered CSV calls.
