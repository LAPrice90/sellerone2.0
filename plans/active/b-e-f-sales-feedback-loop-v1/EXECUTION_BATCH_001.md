# Execution Batch 001

## Title
- Automated actuals for F learning

## Job
- build and publish automatic 30d, 60d, and 90d actuals into:
  - `out/analysis_reports/f_sales_history_learning_actuals_latest.csv`
- prove `F012` can run against that automated actuals path without manual data entry

## Allowed files to change
- `scripts/one_off/BEF002_build_sales_feedback_actuals.py`
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- `tests/test_bef002_build_sales_feedback_actuals.py`
- `tests/test_f012_build_sales_history_learning_pack.py`
- files inside `plans/active/b-e-f-sales-feedback-loop-v1/`

## Expectations

### Output 1 - automatic actuals
- create:
  - `out/analysis_reports/f_sales_history_learning_actuals_latest.csv`
- include:
  - `actual_units_30d`, `actual_profit_30d_gbp`
  - `actual_units_60d`, `actual_profit_60d_gbp`
  - `actual_units_90d`, `actual_profit_90d_gbp`
  - source-state fields for each window

### Output 2 - learning pack rebuild
- run:
  - `scripts/one_off/F012_build_sales_history_learning_pack.py`
- prove it reads the automated actuals file path as default normal-use input

## Tests required
- `python -m py_compile scripts/one_off/BEF002_build_sales_feedback_actuals.py scripts/one_off/F012_build_sales_history_learning_pack.py tests/test_bef002_build_sales_feedback_actuals.py tests/test_f012_build_sales_history_learning_pack.py`
- `pytest tests/test_bef002_build_sales_feedback_actuals.py tests/test_f012_build_sales_history_learning_pack.py -q`
- one-off proof runs:
  - `python scripts/one_off/BEF002_build_sales_feedback_actuals.py`
  - `python scripts/one_off/F012_build_sales_history_learning_pack.py`

## Execution result
- compile:
  - pass
- tests:
  - pass (`5`)
- one-off runs:
  - both pass

## Live proof snapshot
- `f_sales_history_learning_actuals_latest.csv`:
  - `rows_total=58`
  - `rows_summary_basis=0`
  - `rows_operational_baseline=58`
- `F012` run:
  - `rows_total=266`
  - `rows_pending_outcome=266`

## Key finding
- Batch 001 automation works and writes the required dataset.
- Current runtime overlap is still weak:
  - no direct summary-ASIN matches were found in this run (`summary_rows_matched=0`)
- This is now an overlap-recovery problem, not a missing automation problem.

## Sign-off
- `code fix applied`
- `isolated verification passed`
- `live loop verification not applicable yet`

## Next step after sign-off
- run Phase 2 planning with overlap-aware example logic:
  - example pack must classify overlap gaps separately from demand-model errors
