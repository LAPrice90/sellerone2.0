# Execution Batch 014

## Title
- Stocked-SKU current vetting report and 30-days-ago reconstruction

## Job
- answer the business question in a direct report:
  - how are we using current stocked SKUs to decide whether to test a product or not
  - which stocked SKUs pass, watch, or fail today
  - if we had vetted the same stocked SKUs 30 days ago, what would the screen have said
  - what happened in the following 30 days

## Why this batch exists
- the user asked for a commercial report, not another model-plumbing pass.
- the report must stay on the sold-truth universe because that is the only place where decision and real outcome can be shown together.
- the report must avoid fake precision:
  - use pass/watch/reject and starter-size guidance
  - use upper/lower ballparks
  - make sample limits explicit

## Allowed files to change
- `scripts/one_off/F016_build_stocked_sku_vetting_report.py` (new)
- `tests/test_f016_build_stocked_sku_vetting_report.py` (new)
- `plans/active/b-e-f-sales-feedback-loop-v1/CODING_PLAN.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/PLAN_STATUS.md`
- `plans/active/b-e-f-sales-feedback-loop-v1/EXECUTION_BATCH_014.md`
- `WORK_LOG.md`

## Output required

### Output 1 - stocked-SKU report
- create `out/analysis_reports/f_stocked_sku_vetting_report_latest.csv`
- one row per sold-truth stocked SKU with:
  - current commercial decision state
  - current live-test readiness state
  - current actual 30-day units and profit
  - current lower/upper band
  - reconstructed 30-days-ago decision state
  - reconstructed 30-days-ago rank-risk context
  - actual next-30-day outcome
  - decision-vs-outcome label

### Output 2 - summary
- create `out/analysis_reports/f_stocked_sku_vetting_summary_latest.csv`
- required metrics:
  - `rows_total`
  - `current_test_buy_rows`
  - `current_watch_rows`
  - `current_reject_rows`
  - `current_ready_for_live_test_rows`
  - `prior_test_buy_rows`
  - `prior_watch_rows`
  - `prior_reject_rows`
  - `prior_nonzero_units_rows`
  - `prior_nonzero_profit_rows`
  - `prior_good_test_rows`
  - `prior_bad_test_rows`
  - `prior_missed_winner_rows`
  - `prior_avoided_loser_rows`

### Output 3 - readable report
- create `out/analysis_reports/f_stocked_sku_vetting_report_latest.md`
- include:
  - today plan
  - summary metrics
  - first rows to inspect
  - plain-English interpretation

## Tests required
- `python -m py_compile scripts/one_off/F016_build_stocked_sku_vetting_report.py tests/test_f016_build_stocked_sku_vetting_report.py`
- `pytest tests/test_f016_build_stocked_sku_vetting_report.py -q`
- runtime proof:
  - `python scripts/one_off/F016_build_stocked_sku_vetting_report.py`

## Success definition
- `code fix applied`:
  - report builder exists and uses current sold-truth commercial outputs, not manual shell stitching.
- `isolated verification passed`:
  - compile and targeted pytest pass.
- `live loop verification confirmed`:
  - the report writes the row-by-row stocked-SKU output, summary CSV, and markdown note from live repo artifacts.

## Execution result
- status:
  - complete (`ready_with_warnings`)
- code changes:
  - `scripts/one_off/F016_build_stocked_sku_vetting_report.py` added
  - `tests/test_f016_build_stocked_sku_vetting_report.py` added

## Proof snapshot
- compile:
  - `python -m py_compile scripts/one_off/F016_build_stocked_sku_vetting_report.py tests/test_f016_build_stocked_sku_vetting_report.py` -> pass
- tests:
  - `pytest tests/test_f016_build_stocked_sku_vetting_report.py -q` -> pass (`1`)
- runtime:
  - `python scripts/one_off/F016_build_stocked_sku_vetting_report.py` at `2026-04-22T07:51:47Z` -> pass

## Output truth
- report artifacts:
  - `out/analysis_reports/f_stocked_sku_vetting_report_latest.csv` -> `57` rows
  - `out/analysis_reports/f_stocked_sku_vetting_summary_latest.csv` -> `14` metrics
  - `out/analysis_reports/f_stocked_sku_vetting_report_latest.md` -> exists
- current decision split:
  - `current_test_buy_rows=2`
  - `current_watch_rows=1`
  - `current_reject_rows=54`
  - `current_ready_for_live_test_rows=2`
- current live-test-ready rows:
  - `OPER::9188805646` -> `test_buy`
  - `OPER::B0CS3VF4GK` -> `test_buy`
  - `OPER::B001ET78RY` -> `watch`
- reconstructed 30-days-ago split:
  - `prior_test_buy_rows=0`
  - `prior_watch_rows=0`
  - `prior_reject_rows=57`
  - `prior_nonzero_units_rows=0`
  - `prior_nonzero_profit_rows=0`
- reconstructed 30-days-ago outcome comparison:
  - `prior_good_test_rows=0`
  - `prior_bad_test_rows=0`
  - `prior_missed_winner_rows=10`
  - `prior_avoided_loser_rows=47`

## Interpretation
- this report uses the sold-truth stocked-SKU universe because unsold scraped products cannot answer "what happened next".
- the 30-days-ago side is a reconstructed screen, not a frozen archived model snapshot.
- the prior window is zero across the full sold sample:
  - `actual_units_60d == actual_units_30d` for all `57` operational-baseline rows
  - `actual_profit_60d_gbp == actual_profit_30d_gbp` for all `57` operational-baseline rows
- commercial meaning:
  - today we have `2` rows ready for live test and `1` row worth watching.
  - the 30-days-ago sample is too thin to learn starter-sizing from older stocked movement because the prior month is blank across this sold set.

## Sign-off
- `code fix applied`: yes
- `isolated verification passed`: yes
- `live loop verification confirmed`: yes
- next step condition:
  - widen the stocked truth sample beyond the current 30-day-heavy sold set if we want stronger "30 days ago" learning rather than all-red prior-window reconstructions
