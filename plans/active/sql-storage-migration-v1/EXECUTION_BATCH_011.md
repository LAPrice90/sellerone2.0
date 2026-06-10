# Execution Batch 011 - CSV Dependency Map And Retirement Gate

Date: 2026-04-28
Status: runtime report written

## Goal
- Build the factual map for remaining CSV dependencies before retiring or replacing more CSV reads.

## Scope
- Report output:
  - `out/sql_migration/csv_dependency_map.csv`
  - `out/sql_migration/csv_dependency_map_summary.json`
- Tool:
  - `scripts/one_off/P006_build_csv_dependency_map.py`

## Allowed Changes
- `scripts/one_off/P006_build_csv_dependency_map.py`
- `tests/test_p006_build_csv_dependency_map.py`
- `plans/active/sql-storage-migration-v1/*`

## Safety Rules
- This batch is read-only against runtime data except for writing the local report files.
- Do not remove any CSV read until the report classifies it and a flow-owned proof path is defined.
- Do not change Google Sheets.
- Do not restart schedulers or live loops during this batch.

## Verification
- Required isolated command:
  - `python -m pytest tests/test_p006_build_csv_dependency_map.py`
- Required runtime command:
  - `python scripts/one_off/P006_build_csv_dependency_map.py --format text`

## Result
- Code fix applied: yes - added `scripts/one_off/P006_build_csv_dependency_map.py` with output schema validation.
- Isolated verification passed: yes - `python -m pytest tests/test_p006_build_csv_dependency_map.py` passed 2 tests.
- Runtime report written: yes - latest `python scripts/one_off/P006_build_csv_dependency_map.py --format text` wrote `out/sql_migration/csv_dependency_map.csv` and `out/sql_migration/csv_dependency_map_summary.json`.
- Latest report counts after Batch 013: `1282` CSV calls found, `198` registered dependencies, `33` SQL-primary pilot-proven calls, `169` remaining registered CSV dependencies, `793` unresolved dynamic paths, `291` unregistered CSV paths.
- Tooling note: first run undercounted because some source files use a Windows BOM; fixed by reading source as `utf-8-sig`.
