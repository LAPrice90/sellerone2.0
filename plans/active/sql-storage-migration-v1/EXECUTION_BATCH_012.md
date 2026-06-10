# Execution Batch 012 - E002 ROI Snapshot SQL Expansion

Date: 2026-04-28
Status: runtime verification passed

## Goal
- Expand E-flow SQL-primary coverage from sales velocity to ROI snapshot outputs.

## Scope
- Registered datasets:
  - `E.SKU_ROI_SNAPSHOT`
  - `E.SKU_ROI_SNAPSHOT_BY_COUNTRY`
- Compatibility CSV exports:
  - `out/sku_roi_snapshot.csv`
  - `out/sku_roi_snapshot_uk.csv`
  - `out/sku_roi_snapshot_non_uk.csv`
  - `out/sku_roi_snapshot_by_country.csv`
- SQL tables:
  - `e_sku_roi_snapshot`
  - `e_sku_roi_snapshot_uk`
  - `e_sku_roi_snapshot_non_uk`
  - `e_sku_roi_snapshot_by_country`

## Allowed Changes
- `scripts/flows/E/E002_build_roi_snapshot.py`
- `tests/test_e002_build_roi_snapshot.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- Default runtime mode remains `csv`.
- SQL mode is enabled only by `SELLERONE_STORAGE_MODE=sql_primary_csv_export`.
- In SQL-primary mode, all four SQL tables are replaced in one transaction before CSV exports are written.
- E publish remains disabled for proof with `E_WRITE_SHEETS=0`.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_e002_build_roi_snapshot.py tests/test_storage_adapter.py`
- Runtime proof:
  - Owned E cycle with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `E_WRITE_SHEETS=0`, and `E_ENFORCE_CADENCE=0`.

## Result
- Code fix applied: yes - `E002_build_roi_snapshot.py` now writes four SQL ROI tables in one transaction before CSV compatibility exports.
- Isolated verification passed: yes - `python -m pytest tests/test_e002_build_roi_snapshot.py tests/test_storage_adapter.py` passed 13 tests.
- Runtime verification: passed - owned E cycle ran with `SELLERONE_STORAGE_MODE=sql_primary_csv_export`, `E_WRITE_SHEETS=0`, and `E_ENFORCE_CADENCE=0`; E split health reported `0 FAIL` and `0 WARN`.
- Row-count proof: `e_sku_roi_snapshot` `57` matched `out/sku_roi_snapshot.csv` `57`; `e_sku_roi_snapshot_uk` `56` matched `out/sku_roi_snapshot_uk.csv` `56`; `e_sku_roi_snapshot_non_uk` `9` matched `out/sku_roi_snapshot_non_uk.csv` `9`; `e_sku_roi_snapshot_by_country` `65` matched `out/sku_roi_snapshot_by_country.csv` `65`.
