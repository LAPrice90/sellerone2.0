# Execution Batch 032 - E-Owned SQL-Primary Isolated Proof

Started UTC: 2026-04-28T14:55:00Z
Completed UTC: 2026-04-28T15:03:08Z
Status: completed - E-owned SQL-primary proof passed

## Purpose
- Run one E-owned proof cycle after B local proof.
- Keep schedulers disabled.
- Keep Google Sheets publishing disabled.
- Validate E SQL-primary writes and E split health after finalization.

## Preflight Evidence
- AMZ scheduled tasks remained disabled.
- No E lock was present:
  - `out/systems/E/live/E_cycle.lock`
  - `out/E_cycle.lock`
- P002 forced proof planner was run for E and wrote `forced_proof_E.json`.
- Last E split checklist snapshot was clean: `23 ok`, `0 fail`.

## Planned Command
- `python scripts/cycles/run_E_cycle.py`

Environment:
- `SELLERONE_STORAGE_MODE=sql_primary_csv_export`
- `SELLERONE_SQLITE_PATH=out/sql/sellerone_dev.sqlite3`
- `E_ENFORCE_CADENCE=0`
- `E_WRITE_SHEETS=0`

## Results
- First E owned run completed, but rollback validation initially failed `1` table:
  - failing table: `b_phase1_sku_scope`
  - reason: `out/phase1_sku_scope.csv` was refreshed by E-scoped A015 daily-intel logic, but the phase1 scope writer still wrote CSV only.
- Root-cause fix:
  - updated `scripts/phase1/phase1_sku_scope.py` so `write_scope_csv()` uses `write_dataframe_with_sql_compat(..., "b_phase1_sku_scope")`.
  - updated `tests/test_phase1_sku_scope.py` to prove SQL-compatible writing and to provide explicit stock fixtures for current parked-stock semantics.
- Focused tests after fix:
  - `pytest tests/test_phase1_sku_scope.py tests/test_storage_adapter.py tests/test_p007_validate_sql_rollback_exports.py -q`
  - result: `16 passed`
- Current phase1 scope sync:
  - `phase1_scope_rows=608`
  - `phase1_scope_non_parked=157`
  - `phase1_scope_parked=451`
- Rerun E owned proof:
  - `E001_build_sales_velocity.py`: `483` rows, SQL rows `483`
  - `E002_build_roi_snapshot.py`: combined `57` rows, UK `56`, non-UK `9`, by-country `65`
  - `E003_build_restock_signals.py`: `161` rows
  - `E004_build_performance_summary.py`: `161` rows
  - `E005_build_study_report.py`: `161` rows
  - `E006_build_sales_truth_reconciliation.py`: `57` rows, `mismatch_rows=0`, SQL rows `114`
  - `E007_build_sku_daily_sales_truth.py`: `454` rows, `finalized_rows=442`, `provisional_rows=12`
- E scoped health after rerun:
  - checklist: `out/cycle_alerts/checklist_E_split.csv`
  - rows: `23`
  - `split_fail=0`
  - `split_warn=0`
- Rollback validation after rerun:
  - `status=passed`
  - `checked_count=48`
  - `pass_count=48`
  - `fail_count=0`
  - `missing_csv_count=0`
  - `missing_table_count=0`
  - export bundle: `out/sql_migration/rollback_exports_20260428T150231Z`
- Dependency map after fix:
  - `row_count=1245`
  - `registered_dependency_count=156`
  - `sql_primary_pilot_proven_count=164`
  - `csv_dependency_remaining_count=0`
  - `unresolved_dynamic_count=804`
  - `unregistered_csv_count=285`
- Ownership after proof:
  - AMZ scheduled tasks remained disabled.
  - No Python owner process remained.
  - No E or B cycle lock remained.

## Remaining Proof Gap
- E local/owned proof is confirmed.
- Scheduler restoration has not been performed.
- H and A owned proof windows remain.
