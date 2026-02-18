# Script Index (numbered)

## A01 - scripts/A001_run_listings_to_sheet.py
- Purpose: One-click runner for GET_MERCHANT_LISTINGS_ALL_DATA.
- Flow: token -> create report -> poll -> download -> parse -> write Sheets (raw + focus summary) -> snapshot CSV -> update Run_Status row.
- Outputs: Sheets `MerchantListings_raw`, `Listings_focus_summary`, `Run_Status`; file `out/merchant_listings_latest.csv`.
- Modes: RUN_MODE=sheet (default) or RUN_MODE=sku (prints only the target SKU row).
- Config: MARKETPLACE_ID, POLL_INTERVAL, MAX_ATTEMPTS, TARGET_SKU, DEBUG_RAW (optional).

## Core helpers (importable)
- scripts/api/get_merchant_listings_report.py
  - Purpose: Core report fetcher used by 01 (token -> create -> poll -> download -> parse).
  - Test mode: CLI flags to read a local TSV; no Sheets writes.
- scripts/api/get_catalog_items.py
  - Purpose: Catalog Items API call + LWA token helper used by 02.

## A02 - scripts/A002_run_catalog_items_to_sheet.py
- Purpose: Catalog Items API (2022-04-01) fetch + flatten; writes to Sheets/CSV so we can pick columns to keep.
- Flow: read ASINs from `out/merchant_listings_latest.csv` (asin1 or product-id when type=1) -> fetch catalog items with `includedData=images,attributes,summaries,productTypes,identifiers,relationships` -> flatten -> write tab `CatalogItems_raw` -> save `out/catalog_items_flat.csv`.
- Config: MARKETPLACE_ID, MAX_ITEMS, ASIN_SOURCE, SHEET_ID, SHEET_TAB_CATALOG_ITEMS.

## How to run (non-coder friendly)
- Set env vars in `secrets/.env` (marketplace, sheet IDs, tokens).
- From repo root run: `python scripts/001_run_listings_to_sheet.py` or `python scripts/002_run_catalog_items_to_sheet.py`.
- Check `out/` for latest CSV/JSONL snapshots if Sheets is slow.
- If something fails, look at the `Run_Status` tab for the script row; the `alert` column tells you what broke.

## Notes
- Keep runners numbered, keep API calls under scripts/api/, keep outputs in out/.

## A03 - scripts/A003_run_inventory_to_sheet.py
- Purpose: Fetch FBA inventory summaries and keep only active listings (based on seller-sku from out/merchant_listings_latest.csv).
- Flow: read active SKUs -> call inventory summaries (paged) -> filter to active SKUs -> write tab `Inventory_raw` -> snapshot `out/inventory_summaries.csv` -> update Run_Status row.
- Config: MARKETPLACE_ID, INVENTORY_INPUT_CSV, INVENTORY_LIMIT_PAGES (0 = no limit), INVENTORY_SLEEP_SEC.

## A04 - scripts/A004_run_fees_to_sheet.py
- Purpose: Fetch fee estimates at £10 and £100 for each SKU and write fees/margins into Product_DB.
- Flow: read SKUs from Product_DB -> call feesEstimate API twice (price=10 and 100, GBP, FBA) -> update fee_total_10/100, margin_10/100, last_updated_A004 -> snapshot `out/fees_estimates.csv` and refresh Product_DB preview.
- Config: MARKETPLACE_ID, FEES_SLEEP_SEC (optional throttle), LWA creds from env.

## B01 - scripts/B001_run_orders_to_sheet.py
- Purpose: Fetch live orders and order items from SP-API and write to Sheets/CSV.
- Flow: GET orders (orders.getOrders) -> GET items per order (orders.listOrderItems) -> write tabs `Orders_raw` and `OrderItems_raw` -> snapshot CSVs in out/ -> update Run_Status.
- Config: MARKETPLACE_ID, ORDERS_CREATED_AFTER (ISO8601), ORDERS_UPDATED_AFTER (ISO8601), ORDERS_MAX_PER_PAGE.

## B02 - scripts/B002_run_financial_events_to_sheet.py
- Purpose: Fetch posted financial events and aggregate shipment fees per order.
- Flow: GET finances.listFinancialEvents (posted) -> flatten charges/fees -> write tabs `FinancialEvents_raw` and `FinancialFees_summary` -> snapshot CSVs in out/ -> update Run_Status.
- Config: FIN_POSTED_AFTER, FIN_POSTED_BEFORE, FIN_MAX_RETRIES, FIN_SLEEP_SEC.

## B04 - scripts/B004_build_order_audit.py
- Purpose: Build `order_audit_split.csv` in the legacy schema from the latest Orders_raw/OrderItems_raw snapshots.
- Flow: read `out/orders_raw.csv` and `out/order_items_raw.csv` -> flatten per order item with audit columns -> write `out/order_audit_split.csv`.
- Config: none (reads latest snapshots).

## C01 - scripts/one_off/T012_C001_seed_product_db.py
- Purpose: Create a `Product_DB` tab with manual + auto fields; no data overwrite.
- Flow: if tab missing, create with headers (manual: VAT/status/supplier/pricing/pack sizes/notes; auto: catalog + stock fields). If tab exists, leave it untouched.
- Config: SHEET_ID from env or default in script.

## C02 - scripts/C002_import_manual_product_data.py
- Purpose: Import manual product data (supplier/supply code/discontinued/drop/barcode) into `Product_DB` without touching other manual fields.
- Flow: read `reference/manual_product_data.tsv` (or CSV via PRODUCT_MANUAL_FILE env) with headers seller_sku, asin, supplier, barcode, supply_code, discontinued, drop -> upsert into `Product_DB` (sets supplier_name, supplier_code, sale_status, barcode).
- Config: PRODUCT_MANUAL_FILE (optional, defaults to reference/manual_product_data.tsv).

## TEMP / one-off helpers
- H001_set_health_alert_snooze.py - set, clear, or view health-check toast snooze (`out/locks/health_alert_snooze.json`).
- C001_seed_product_db.py — only needed if the Product_DB tab is rebuilt/empty.
- C002_import_manual_product_data.py — run ad-hoc when manual TSV/CSV changes.
- B004_build_order_audit.py — ad-hoc audit export (legacy format).
