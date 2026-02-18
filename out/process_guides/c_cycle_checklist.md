# C Cycle Execution Checklist

Use this checklist when you are running or validating the C cycle. The runbook explains the system. This is the step-by-step execution list.

## Before you start
- A015 health check shows FAIL = 0.
- A/B cycles are not running.
- Inputs exist:
  - out/financial_events_shipments.csv
  - out/financial_events_inbound_summary.csv
  - out/inventory_ledger_raw.csv
  - reference/Amazon Supplier Process - Orders (3).csv (or current purchase source)
  - out/merchant_listings_latest.csv
  - out/fba_storage_fee_charges_monthly.csv (monthly, if available)

## Run steps (local only)
1) Run schema checks for all inputs.
2) Pull monthly storage fee report (C007, monthly, after the 10th).
3) Pull long-term storage fee report (C008, monthly, after the 15th).
4) Pull inbound shipment contents (C009).
   - If C009 falls back to Inventory Ledger, note "receipts-only" and treat missing-units as not done.
5) Build inbound delivery status (C001).
6) Build inbound missing units (C002).
7) Build inbound cost events (C003).
8) Build inbound cost allocations (C004).
9) Allocate shipment costs to SKU (C005).
10) Build token maturity window (C006).
11) Build storage fee by SKU (monthly).
12) Run C health checks (C015).

## Validation gates
- Schema checks all pass.
- Inbound coverage >= 95 percent.
- If C009 is receipts-only, mark Missing Units as "not done" (do not claim planned vs received).
- Storage fee SKU mapping >= 95 percent (WARN if below).
- Unallocated costs bucket is present and non-negative.

## Publish (only if all gates pass)
- Publish C outputs to the C sheet in one staged write (requires `C_WRITE_SHEETS=1` and `C_SHEET_ID`).
- Record run timestamp in the C sheet log tab.

## After run
- Re-run A015 to ensure no new FAILs.
- File results under date in out/reports if needed.

## If any gate fails
- Stop and fix the input or mapping.
- Do not publish partial outputs.
- Record the failure reason in the run log.
