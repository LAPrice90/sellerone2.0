# Execution Batch 000

## Title
- Truth freshness and operational bridge foundation

## Job
- build the first trustworthy foundation layer for a self-feeding sales feedback machine

## Why this batch is first
- right now we already have sales truth, but we do not yet have:
  - a freshness-safe foundation
  - a valid bridge into the F learning universe
- if we skip this step, later automation will either go stale or join the wrong rows

## Allowed files to change
- `scripts/one_off/BEF000_build_sales_truth_foundation.py`
- `scripts/one_off/BEF001_build_operational_feedback_seed.py`
- `tests/test_bef000_build_sales_truth_foundation.py`
- `tests/test_bef001_build_operational_feedback_seed.py`
- files inside `plans/active/b-e-f-sales-feedback-loop-v1/`

## Expectations

### Output 1 - foundation mart
- create:
  - `out/analysis_reports/bef_sales_truth_foundation_latest.csv`
- it must show, at minimum:
  - operational SKU
  - ASIN when available
  - latest finalized date
  - latest provisional date
  - `order_master` timestamp
  - `order_ledger_fx` timestamp
  - lag minutes
  - truth state
  - stale flag

### Output 2 - operational replay seed
- create:
  - `out/analysis_reports/bef_operational_feedback_seed_latest.csv`
- it must show, at minimum:
  - ASIN
  - operational SKU
  - recent sales presence
  - bridge status
  - ambiguity flag

### Output 3 - health view
- create:
  - `out/analysis_reports/bef_sales_feedback_health_latest.csv`
- it must show, at minimum:
  - freshness warn or fail counts
  - bridge resolved, ambiguous, and unresolved counts
  - total in-scope operational rows

## Tests required
- `python -m py_compile scripts/one_off/BEF000_build_sales_truth_foundation.py scripts/one_off/BEF001_build_operational_feedback_seed.py tests/test_bef000_build_sales_truth_foundation.py tests/test_bef001_build_operational_feedback_seed.py`
- `pytest tests/test_bef000_build_sales_truth_foundation.py tests/test_bef001_build_operational_feedback_seed.py -q`
- one-off proof runs:
  - `python scripts/one_off/BEF000_build_sales_truth_foundation.py`
  - `python scripts/one_off/BEF001_build_operational_feedback_seed.py`

## Pass checks
- all required output files exist
- stale lag is measured, not hidden
- unresolved bridge rows are explicit
- no direct forbidden `seller_sku -> sku` assumption exists
- no sheets or DB paths are touched

## Sign-off
- `code fix applied`
- `isolated verification passed`
- `live loop verification not applicable yet`

## Next step after sign-off
- start Batch 001:
  - automatic actuals for F learning
