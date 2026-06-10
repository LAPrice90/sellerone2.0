# Execution Batch 007 Reply

## Status
- Complete / Partial / Failed:
  - complete
- Checked against:
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_007.md`

## Summary of work done
- Built one-off post-purchase learning pack owner:
  - `scripts/one_off/F012_build_sales_history_learning_pack.py`
- Added scoped tests for:
  - missing-actuals pending outcome handling
  - inferred demand-too-high / demand-too-low outcome classification
  - append-safe upsert behavior with operator outcome override
- Emitted the learning outputs:
  - `out/systems/F/live/feeder_sales_history_learning_live.csv`
  - `out/analysis_reports/f_sales_history_learning_review_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_health_latest.csv`
  - `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv`

## Isolated verification
- command:
  - `pytest -q tests/test_f012_build_sales_history_learning_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f002_build_backtest_calibration_set.py`
- result:
  - `13 passed`
- compile check:
  - `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py scripts/one_off/F012_build_sales_history_learning_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f012_build_sales_history_learning_pack.py`
  - pass

## One-off proof run
- command:
  - `python scripts/one_off/F012_build_sales_history_learning_pack.py --observed-utc 2026-04-20T13:02:00Z`
- result:
  - `status=success`
  - `rows_total=266`
  - `rows_pending_outcome=266`

## Output proof
- learning log:
  - `feeder_sales_history_learning_live.csv`
  - rows: `266`
- review output:
  - `f_sales_history_learning_review_latest.csv`
  - rows: `266`
- health output:
  - `f_sales_history_learning_health_latest.csv`
  - rows: `14`
- actuals template:
  - `f_sales_history_learning_actuals_template_latest.csv`
  - rows: `266`

## Health proof
- `rows_with_actuals_30d=0`
- `rows_with_actuals_60d=0`
- `rows_with_actuals_90d=0`
- `rows_with_outcome=0`
- `rows_pending_outcome=266`
- `outcome::pending_outcome=266`

## Required status language
- `code fix applied`
- `isolated verification passed`
- `live loop verification not required`
- `runtime promotion not attempted in this ticket`
