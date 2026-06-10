# Execution Batch 013 - E003/E004/E005 Analytics SQL Expansion

Date: 2026-04-28
Status: runtime verification passed

## Goal
- Expand E-flow SQL-primary coverage through the restock, performance summary, and study report writers.

## Scope
- Registered datasets:
  - `E.SKU_RESTOCK_SIGNALS`
  - `E.SKU_PERFORMANCE_SUMMARY`
  - `E.STUDY_REPORT`
- Compatibility CSV exports:
  - `out/sku_restock_signals.csv`
  - `out/sku_performance_summary.csv`
  - `out/e_study_report.csv`
- SQL tables:
  - `e_sku_restock_signals`
  - `e_sku_performance_summary`
  - `e_study_report`

## Allowed Changes
- `scripts/flows/E/E003_build_restock_signals.py`
- `scripts/flows/E/E004_build_performance_summary.py`
- `scripts/flows/E/E005_build_study_report.py`
- `tests/test_e003_build_restock_signals.py`
- `tests/test_e004_build_performance_summary.py`
- `tests/test_e005_build_study_report.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- SQL-primary mode writes SQL before the existing CSV compatibility export.
- E publish remains disabled for proof with `E_WRITE_SHEETS=0`.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_storage_adapter.py`
- Runtime proof:
  - Owned E cycle with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `E_WRITE_SHEETS=0`, and `E_ENFORCE_CADENCE=0`.

## Result
- Code fix applied: yes - `E003_build_restock_signals.py`, `E004_build_performance_summary.py`, and `E005_build_study_report.py` now write SQL before CSV compatibility exports in SQL-primary mode.
- Isolated verification passed: yes - `python -m pytest tests/test_e003_build_restock_signals.py tests/test_e004_build_performance_summary.py tests/test_e005_build_study_report.py tests/test_storage_adapter.py` passed 14 tests.
- Runtime verification: passed - owned E cycle ran with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `E_WRITE_SHEETS=0`, and `E_ENFORCE_CADENCE=0`; E split health reported `0 FAIL` and `0 WARN`.
- Row-count proof: `e_sku_restock_signals` `161` matched `out/sku_restock_signals.csv` `161`; `e_sku_performance_summary` `161` matched `out/sku_performance_summary.csv` `161`; `e_study_report` `161` matched `out/e_study_report.csv` `161`.
