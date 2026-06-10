# Project Brief

## Title
- B/E/F sales feedback loop

## Why this exists
- We already have real 30-day sales truth inside B and E.
- F still treats actual post-decision results as a manual or partially manual follow-up.
- Current supplier-scan outputs do not directly overlap with the operational SKU universe, so "automatic learning" is not yet a real closed loop.

## What this phase must achieve
- Turn B/E sales truth into the automatic actuals source for F learning.
- Separate finalized truth from provisional truth so same-day data does not get mistaken for settled economics.
- Build an explicit bridge from operational catalog items to the F review universe.
- Leave the user doing only one thing:
  - checking logic decision examples

## What this phase must not do
- no Google Sheets writes
- no local DB rewrites
- no ad-hoc A runs
- no hidden downstream smoothing to make outputs look better
- no daily-loop promotion until one-off proof is clean

## Current evidence that matters
- `out/order_master.csv` is updating during the day.
- `out/order_ledger_fx.csv` and E truth outputs are not guaranteed to refresh in step with it.
- `out/sku_daily_sales_truth_latest.csv` already separates:
  - `finalized_ledger`
  - `provisional_order_master`
- `out/systems/F/live/feeder_backtest_summary_live.csv` has no direct overlap with operational B/E SKU keys.

## End state
- one canonical actuals path
- one explicit bridge path
- one automated learning pack
- one operator review pack
- no manual actuals typing for normal feedback use
