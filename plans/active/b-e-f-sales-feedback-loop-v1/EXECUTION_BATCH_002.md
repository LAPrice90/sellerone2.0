# Execution Batch 002

## Title
- Overlap-aware operator example pack

## Job
- build and publish:
  - `out/analysis_reports/bef_sales_feedback_examples_latest.csv`
- classify each learning row so operator review can separate:
  - overlap/data-coverage gaps
  - true demand-model errors
  - right-call confirmations

## Allowed files to change
- `scripts/one_off/BEF003_build_sales_feedback_examples.py`
- `tests/test_bef003_build_sales_feedback_examples.py`
- files inside `plans/active/b-e-f-sales-feedback-loop-v1/`

## Expectations

### Output 1 - example pack
- create:
  - `out/analysis_reports/bef_sales_feedback_examples_latest.csv`
- each row must include:
  - expected result
  - actual result
  - outcome class
  - supporting notes

### Output 2 - overlap-aware outcome classes
- classify `pending_outcome` rows into:
  - `overlap_gap_no_summary_match`
  - `no_operational_truth_coverage`
  - `pending_window_not_ready`
- classify non-pending rows into:
  - `model_error_demand_too_high`
  - `model_error_demand_too_low`
  - `model_error_other`
  - `right_call`

## Tests required
- `python -m py_compile scripts/one_off/BEF003_build_sales_feedback_examples.py tests/test_bef003_build_sales_feedback_examples.py`
- `pytest tests/test_bef003_build_sales_feedback_examples.py -q`
- one-off proof run:
  - `python scripts/one_off/BEF003_build_sales_feedback_examples.py`

## Execution result
- compile:
  - pass
- tests:
  - pass (`2`)
- one-off run:
  - pass

## Live proof snapshot
- `bef_sales_feedback_examples_latest.csv`:
  - `rows_total=266`
  - `example_class::no_operational_truth_coverage=266`
  - sample row includes:
    - `expected_result=expected_units_next_30d=2; expected_profit_next_30d_gbp=68.24`
    - `actual_result=actuals_pending`
    - `example_class=no_operational_truth_coverage`

## Key finding
- Batch 002 builder works and produces the required explainable example output.
- Current runtime outcome is fully coverage-gap driven:
  - all rows classify as `no_operational_truth_coverage`
- This confirms the immediate bottleneck is overlap/bridge coverage, not demand classification logic.

## Sign-off
- `code fix applied`
- `isolated verification passed`
- `live loop verification not applicable yet`

## Next step after sign-off
- run Phase 3 guarded automation planning and implementation batch definition
