# Execution Batch 015

## Title
- Sellerboard order-alignment investigation for sales truth

## Job
- investigate why our local sold-truth layers are missing orders or undercounting units versus Sellerboard.
- focus on order alignment to Sellerboard for:
  - unit counts
  - sales values
  - order presence
- allow expected tolerances for:
  - fee timing and fee estimates
  - COGS timing and COGS basis
- do not treat small fee or COG differences as the primary defect if order presence or units are wrong.

## Why this batch exists
- the current pass/fail outputs are not reliable until order alignment is fixed.
- proof case:
  - `B07L6H9GZ2` shows `20` units in Sellerboard order items for `2026-03-23` to `2026-04-21`
  - our sold-truth pack reports `4`
  - our `sku_daily_sales_truth_latest.csv` reports `4`
  - direct ledger inspection already proves more shipped orders exist than the sold-truth layer captured
- until this is fixed, commercial screening is using wrong sales truth on at least some SKUs.

## Primary reference files
- `reference/DRJ_Hardware_Dashboard_Order_Items_23_03_2026-21_04_2026_(2026_04_22_10_05_26_439).csv`
- `reference/DRJ_Hardware_Dashboard_Products_23_03_2026-21_04_2026_(2026_04_22_09_41_46_840).csv`

## Root-cause questions to answer
- which order rows in Sellerboard are missing from our local truth layers
- whether the miss is caused by:
  - order ingestion
  - transaction-to-daily aggregation
  - SKU or ASIN mapping
  - finalized/provisional filtering
  - date-window cutoffs
  - refund handling
  - shipping or other transaction-type treatment
- whether the issue is broad or limited to specific SKUs or date ranges

## Expectations

### Output 1 - alignment audit
- produce a machine-readable comparison between Sellerboard order items and our local order truth for the same window.
- compare at least:
  - order id
  - order date
  - ASIN
  - SKU
  - units
  - sales value
  - refund indicator

### Output 2 - discrepancy classification
- classify each discrepancy into one of:
  - missing_local_order
  - unit_mismatch
  - sales_value_mismatch
  - sku_map_mismatch
  - asin_map_mismatch
  - date_window_mismatch
  - refund_handling_mismatch
  - expected_fee_or_cogs_tolerance_only

### Output 3 - root-cause proof
- identify the earliest broken stage in the pipeline.
- show exact examples with row-level evidence.
- include at least one worked proof case for `B07L6H9GZ2`.

### Output 4 - fix and rerun
- implement the smallest upstream fix that restores order alignment.
- rerun the affected one-off build chain.
- then rerun the sold-truth report so pass/watch/reject can be rechecked from corrected sales truth.

## Files allowed to change
- scripts and tests in the upstream sales-truth build path only
- this active plan folder
- `WORK_LOG.md`

## Non-goals
- no Google Sheets writes
- no local DB manual alignment
- no downstream result-masking
- no changing thresholds to hide missing orders

## Proof required
- before fix:
  - count Sellerboard orders and units for the comparison window
  - count local orders and units for the same window
  - show mismatch examples
- after fix:
  - show corrected local counts
  - show remaining tolerated differences separately
  - rerun the current stocked-SKU vetting report and compare pass totals

## Success definition
- order presence and units align materially to Sellerboard for the comparison window
- remaining differences are mostly fee/COG timing or other accepted tolerance classes
- `B07L6H9GZ2` no longer shows an obvious undercount in our truth layer
- updated pass/watch/reject outputs can be trusted for re-review

## Prompt for separate conversation
Use this exact task:

```text
Ticket: B-E-F Batch 015 Sellerboard order-alignment investigation

We have found that our sold-truth layer is undercounting some SKUs versus Sellerboard, and this is now blocking trust in our pass/fail outputs.

Main proof case:
- ASIN `B07L6H9GZ2`
- Sellerboard order items for `2026-03-23` to `2026-04-21` show `20` units
- our current sold-truth report shows `4`
- our `sku_daily_sales_truth_latest.csv` also shows `4`

Task:
1. Study these reference files:
- `reference/DRJ_Hardware_Dashboard_Order_Items_23_03_2026-21_04_2026_(2026_04_22_10_05_26_439).csv`
- `reference/DRJ_Hardware_Dashboard_Products_23_03_2026-21_04_2026_(2026_04_22_09_41_46_840).csv`

2. Compare Sellerboard order-item truth to our local truth layers for the same window.
Focus mainly on:
- order presence
- unit counts
- sales values

3. Treat these as tolerated or secondary unless they explain missing orders:
- fee estimates
- fee timing
- COGS timing
- COGS basis differences

4. Find the earliest broken stage in our pipeline.
Root-cause first. Do not patch downstream outputs to make results look right.

5. Produce row-level proof for why orders are missing.
At minimum, fully work through `B07L6H9GZ2`.

6. Implement the smallest upstream fix.

7. Rerun the affected builders and then rerun:
- `out/analysis_reports/f_stocked_sku_vetting_report_latest.csv`

8. Report:
- Sellerboard order/unit totals before fix
- local order/unit totals before fix
- discrepancy classes
- exact root cause
- post-fix totals
- updated pass/watch/reject counts

Repo rules:
- no Google Sheets writes
- no local DB manual alignment
- no downstream masking
- explain in plain English
- show proof before calling it fixed

Expected outcome:
- order alignment to Sellerboard data is materially corrected for sales values and numbers
- only tolerated fee/COGS discrepancies remain
- once fixed, we can recheck pass data from corrected truth
```
