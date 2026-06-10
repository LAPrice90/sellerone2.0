# Data Contracts

## 1) `product_db_operator_view.csv`
Path:
- `out/systems/O/live/product_db_operator_view.csv`

Purpose:
- one merged read-friendly row per SKU for the product database browse page

Required fields:
- `asof_utc`
- `seller_sku`
- `asin`
- `title`
- `main_image`
- `supplier_code`
- `supplier_name`
- `supplier_sku`
- `barcode`
- `sale_status`
- `queue_status`
- `operational_status`
- `status_reason`
- `supplier_pack_size`
- `amazon_pack_size`
- `order_qty_mode`
- `sell_pack_qty`
- `supplier_case_qty`
- `supplier_case_multiple`
- `valid_order_step`
- `pack_conversion_note`
- `moq`
- `supplier_catalog_price`
- `last_purchase_price`
- `vat_rate`
- `stock_available`
- `stock_total`
- `ordered_open_qty`
- `velocity_30d`
- `days_cover`
- `roi_snapshot_pct`
- `data_issue_flags`

Notes:
- fixed editable truth and derived read-only truth must coexist in one row, but ownership must stay explicit in code and UI
- `operational_status` is the displayed status badge on the browse page
- `data_issue_flags` should surface things like missing pack truth, missing cost truth, or stale source inputs

## 2) `product_db_edit_events.csv`
Path:
- `out/systems/O/inbox/product_db_edit_events.csv`

Purpose:
- operator edit submissions from the separate edit page

Required fields:
- `event_utc`
- `event_id`
- `seller_sku`
- `asin`
- `actor`
- `source_reference`
- `edit_note`
- `sale_status`
- `supplier_code`
- `supplier_name`
- `supplier_sku`
- `barcode`
- `supplier_pack_size`
- `amazon_pack_size`
- `order_qty_mode`
- `sell_pack_qty`
- `supplier_case_qty`
- `supplier_case_multiple`
- `valid_order_step`
- `repack_required`
- `bundle_required`
- `pack_conversion_note`
- `moq`
- `supplier_catalog_price`
- `last_purchase_price`
- `target_margin`
- `vat_rate`
- `notes`

Notes:
- one row should represent one submitted edit snapshot for one SKU
- do not send field-by-field mini-events for this workflow
- this file is an inbox, not proof of applied truth

## 3) `product_db_edit_holds.csv`
Path:
- `out/systems/O/live/product_db_edit_holds.csv`

Purpose:
- explicit validation failures for edit submissions

Required fields:
- `event_utc`
- `event_id`
- `seller_sku`
- `hold_reason`
- `hold_detail`
- `actor`

Notes:
- use this instead of silent rejection
- hold reasons should be plain and operator-readable

## 4) Ownership split
- Fixed editable truth:
  - supplier identity
  - supply code and barcode
  - pack and batch rules
  - VAT and target-margin settings
  - sale status and notes
- Derived read-only truth:
  - stock
  - ordered open quantity
  - velocity
  - days cover
  - ROI snapshot
  - live listing price and downstream economics overlays where present
- Overlay status truth:
  - `operational_status`
  - combines fixed `sale_status` and current O queue state for display
