# C Cycle Runbook - Inbound Shipments + Cost Linking

This runbook defines the C cycle. C is a daily, slow cadence loop focused on inbound shipments, SKU cost linkage, and storage fee breakdowns. C does not touch Order_Master or tokens. It is reporting and linking only.

## Purpose
- Track inbound shipment completion by shipment ID.
- Provide Sellerboard-style inbound progress (percent received).
- Detect missing units at shipment and SKU level.
- Link inbound units to SKU costs for supplier and SKU P and L.
- Add monthly FBA storage fee charges by SKU.
- Provide clean, testable outputs for analysis and downstream reporting.

## Blunt truths (do not ignore)
1) Not every fee can be linked to a SKU or shipment by Amazon data alone. Some finance lines do not carry shipment IDs or SKUs. Do not force-link them. Keep an unallocated bucket and treat it as normal until keys exist.
2) Inbound v0 vs v2024 is messy. Build dual-path support and use AUTO mode to read whichever is available.
3) Perfect linkage (tokens to shipments to costs) requires you to store a shipment_id in your own receipts intake. API data alone will not guarantee perfect joins.
4) Inbound v2024 is async. You must poll operation status and only continue after SUCCESS to avoid false missing-units signals.
5) Shipment items are not guaranteed in getShipment. Always call listShipmentItems for item details.
6) If the inbound shipment contents report is blocked (403 Unauthorized), C009 will fall back to Inventory Ledger receipts. This keeps C running, but missing-units becomes receipts-only and does not reflect planned vs received. Treat this as "not done" until Reports API access is restored.

## Inbound shipment contents status (current reality)
- Primary source: Reports API inbound shipment contents report.
- If blocked: fallback to Inventory Ledger receipts.
- Consequence: Missing units will be empty or 0 because planned quantities are unknown.
- Action to finish: restore Reports API access for the inbound shipment report, then rerun C009, C001, C002, and publish.

## Inputs (must exist before C runs)
- `out/financial_events_shipments.csv`
- `out/financial_events_inbound_summary.csv`
- `out/inventory_ledger_raw.csv`
- `reference/Amazon Supplier Process - Orders (3).csv` (or current purchase source)
- `out/merchant_listings_latest.csv` (for SKU to ASIN mapping)
- Storage fee report file (monthly):
  - `out/fba_storage_fee_charges_monthly.csv` from SP API report `GET_FBA_STORAGE_FEE_CHARGES_DATA`

## Outputs (local first, sheet later)
- `out/inbound_delivery_status.csv`
- `out/inbound_cost_events.csv`
- `out/inbound_costs_allocated.csv`
- `out/inbound_costs_unallocated.csv`
- `out/inbound_costs_allocated_sku.csv`
- `out/inbound_costs_unallocated_sku.csv`
- `out/inbound_costs_allocation_summary.csv`
- `out/fba_storage_fee_charges_monthly.csv` (raw parsed)
- `out/storage_fee_by_sku_monthly.csv`
- `out/inbound_missing_units.csv`
- `out/token_maturity_window.csv`
- `out/token_maturity_window_sku.csv`

## What C Must Not Do
- Do not write to Order_Master.
- Do not write to token ledger.
- Do not allocate tokens or adjust inventory counts.

## C Cycle Steps
1) Pull storage fee report (monthly, after the 10th).
2) Validate schemas for all inputs.
3) Build inbound delivery status (shipment percent received).
4) Build missing units report (shipment and SKU gaps).
5) Build inbound cost events.
6) Allocate inbound costs to shipments (unallocated bucket stays separate).
7) Link storage fees to SKU and supplier (keep unallocated bucket).
8) Build token maturity window dataset (for health tests).
9) Write local outputs.
10) If sheets are enabled, publish all C outputs in one staged write.

## Manual one-run (no publish)
If you want to run C once from the terminal without writing sheets:
- Set `C_SKIP_PUBLISH=1`
- Run `python scripts/run_C_cycle.py`

## Storage Fee Report (monthly)
ReportType: `GET_FBA_STORAGE_FEE_CHARGES_DATA`
Timing: run after the 10th of each month for the previous month.
Override: set `STORAGE_FEE_OVERRIDE_YEAR` and `STORAGE_FEE_OVERRIDE_MONTH` to force a past month.
Accounting rule: record the storage fee on the charge date (around the 10th) and do not backdate prior months.
Expected columns:
- asin or fnsku

## Long Term Storage (Aged Inventory Surcharge)
ReportType: `GET_FBA_FULFILLMENT_LONGTERM_STORAGE_FEE_CHARGES_DATA`
Timing: run after the 15th of each month for the previous month.
Override: set `LTSF_OVERRIDE_YEAR` and `LTSF_OVERRIDE_MONTH` to force a past month.
Accounting rule: record the fee on the charge date (around the 15th) and do not backdate prior months.
Output: `out/fba_long_term_storage_fee_charges_monthly.csv`
- average-quantity-on-hand
- estimated-monthly-storage-fee
- storage-utilization-ratio
- utilization-surcharge-rate

## Inbound API sources (AUTO dual-path)
- Legacy v0: shipment lists and items (if still available).
- v2024-03-20: inbound plans and shipment detail.
AUTO mode chooses the available path and logs which one was used.

## v2024 async guardrails (must follow)
- When a v2024 call returns operationId, poll getInboundOperationStatus until status is SUCCESS.
- Do not proceed to missing-units checks until the operation is SUCCESS.
- If status is FAILED, log and move to unallocated or skipped state.

## Tests (A015 health check adds C items)
Required checks:
- Schema checks for all inputs and outputs.
- Coverage checks:
  - inbound rows with cost link >= 95 percent
  - storage fee rows with SKU mapping >= 95 percent
- Missing storage fee rows for active SKUs is WARN, not FAIL.
- Unallocated costs must be tracked and reported, not silently dropped.

## Finance linking rule (v2024 Transactions)
- Only link a cost to a shipment when Context has shipmentId.
- If shipmentId is missing, the cost goes to unallocated bucket.

## Definition of Done for C
- All schema checks pass.
- Coverage checks pass.
- Outputs are generated locally.
- If sheets are enabled, staged publish completes with no partial writes.

## Phase 6 (staged publish + schedule)
- Use `scripts/run_C_cycle.py` for the daily run.
- It uses the shared run lock `out/run_cycle.lock`.
- It runs C001-C006, then A015 as the gate.
- Publish is skipped unless `C_WRITE_SHEETS=1` and `C_SHEET_ID` is set.
- WARN does not publish unless `C_PUBLISH_ALLOW_WARN=1`.

## Build order (do not change)
1) C001 + C002: shipments status and missing units.
2) C015: schema + sanity + publish gate for C.
3) C003 + C004: cost events and link to shipment IDs where possible, unallocated bucket.
4) C005: allocation down to SKU with sum-to-total guardrails.
5) C006: token maturity window + manual token exclusion rules.

## Missing-units guardrail (token maturity)
- Do not alert on missing units until shipment status is CLOSED and updatedDate is at least 14 days old.
- This prevents false positives while shipments are still receiving.

## Checklist to complete C implementation
1) Guidebook approved.
2) Raw input schema validators added.
3) Local outputs produced and verified.
4) A015 health checks updated for C.
5) New sheet created for C outputs.
6) C is added to schedule with run lock.
