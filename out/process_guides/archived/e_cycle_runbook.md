# E Cycle Runbook (Sales Performance)

## Purpose (plain English)
The E cycle builds the daily SKU performance view: sales velocity, ROI, stock-out aware averages, and restock signals. It does not change orders, tokens, or prices. It only reads data and writes reports.

## Inputs (read-only)
- out/order_master.csv
- out/token_cogs_ledger.csv
- out/inventory_summaries.csv
- out/financial_events_level3_summary.csv (if present)
- out/storage_fee_charges_monthly.csv (optional)
- out/long_term_storage_fee_charges_monthly.csv (optional)

## Outputs (local)
- out/sku_sales_velocity.csv
- out/sku_roi_snapshot.csv
- out/sku_restock_signals.csv
- out/sku_performance_summary.csv

## Outputs (Sheets)
- E_Sales_Velocity
- E_ROI_Snapshot
- E_Restock_Signals
- E_Performance_Summary

## Core rules
- Velocity must stop counting days when stock is 0. We only measure days in stock.
- ROI uses actual COGS from tokens, not estimates.
- If COGS is missing, ROI is blank and flagged.
- No writes to Order_Master or tokens.

## Frequency
- Daily after B finishes.
- Safe to rerun (idempotent).

## Failure rules
- If required inputs are missing, E cycle stops and logs a FAIL.
- If stock-out aware velocity cannot be computed, E cycle stops and logs a FAIL.

## Where it fits
- Run after A and B are done.
- Uses latest Order_Master and token COGS.
