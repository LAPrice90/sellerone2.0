# Notes / Future Jobs

- Add missing-SKUs warning to A003 Run_Status when inventory rows < active listings.
- Add sales-linked sanity check: if stock drop exceeds recent sales, flag alert.
- Consider per-SKU inventory fetch fallback status logging (which SKUs failed).
- Add summary tab for any new flows (e.g., sales/orders) to `Listings_focus_summary` with script codes.
- Future: auto-delete dropped stock via API only after return window passes (ensure no recent orders in return period).
- Product DB future fields/logic: VAT status, sale status (active/dropped/discontinued), supplier code, supplier name, supplier pack size, Amazon pack size, conversions both ways, last purchase price, supplier catalog price for price-rise alerts/viability, MOQ, target margin, notes.
- Fees plan: use actual order fees when transactions arrive; use fee estimates (A004) only to backfill SKUs with no transactions after X days.
- Refund handling: Level 3 refund mapping exists but is deferred; re-enable full refund reconciliation later.
- Returns tracking: add Returns/FBA Returns data to determine if refunded items returned to inventory (sellable/unsellable).
- Inbound transportation fees: add shipment-to-SKU allocation logic later (currently no SKU link).

## To-Do / Pass Checklist
- [ ] A003: add missing-SKUs warning in Run_Status when inventory rows < active listings; note missing count.
- [x] B001: live orders/items runner (orders.getOrders + listOrderItems) → Sheets `Orders_raw`/`OrderItems_raw`, CSV snapshots, Run_Status.
- [x] B002: financial events (finances.listFinancialEvents) → raw + per-order fee buckets; summary tab; Run_Status.
- [x] B003: fee estimate fallback (pricing/feesEstimate) for orders without posted shipments; mark estimates; Run_Status.
- [x] B004: orders finance rollup (items + fees) → `OrderFinance_summary`, CSV snapshot, update `Listings_focus_summary` rows tagged B004; Run_Status.
- [ ] Product DB scaffold: `Product_DB` tab with manual fields (VAT status, sale status, supplier code/name, pack sizes/conversions, last purchase price, supplier catalog price, MOQ, target margin, notes) and auto fields from A-scripts (title, brand, main_image, size, dims/weight, stock).
- [ ] Future: auto-delete dropped stock post-return window (no recent orders within return period).
- [ ] Fees: switch to actual posted fees per order; run A004 only as a backfill for SKUs with no transactions after X days (store fee_total_10/100, margin_10/100).
- [ ] SKU fee overrides needed (ASIN vs SKU rates/fees differ): B006PFN3BW / A2-T2AC-TW3L; B007R2ICTK / WX-L5UA-UB1Q.

## Testing Plan (per task)
- A003 missing-SKUs alert: run A003 with known active SKUs; check Run_Status for alert and missing count; verify Inventory_raw retains rows.
- B001: run with a small time window; verify `Orders_raw`/`OrderItems_raw` tabs populated, CSV snapshots written, Run_Status updated.
- B002: run over same window; verify raw financial events tab populated, per-order fee buckets match known orders, summary tab updated, Run_Status reflects status.
- B003: simulate orders without shipment events; ensure estimates are written and flagged; Run_Status updated.
- B004: run after B001/B002/B003; verify per-order rollup matches sums of items + fees, summary tab rows tagged B004, CSV snapshot written, Run_Status updated.
- Product DB scaffold: create tab with headers; ensure A-scripts do not overwrite manual fields; verify auto fields populate when wired.
