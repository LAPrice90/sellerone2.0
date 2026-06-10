# UI Blueprint

## 1) Product database page purpose
- This page is the product truth browser.
- It is not the reorder page.
- It is not the edit page.
- It is the place to understand one SKU quickly and decide whether anything needs maintenance.

## 2) Core design rules
- Browse first, edit second.
- Show only the fields needed for quick scanning in the main list.
- Put deeper detail behind expansion or a side detail view.
- Use one displayed status badge, not several competing raw statuses.
- Keep money, packs, stock, and supplier truth easy to compare across rows.

## 3) Page layout

### Top summary strip
Show fixed count tiles:
- Live
- Snoozed
- Discontinued
- Dropped
- Missing pack truth
- Missing cost truth

These are counts only, not mini dashboards.

### Filter bar
Always visible:
- Search: SKU, ASIN, title, barcode, supply code
- Supplier
- Status
- Pack mode
- VAT rate
- Issues only toggle
- Low stock toggle

Optional:
- Group by `None`, `Supplier`, `Status`

### Main list
Dense rows only.

Recommended glance columns:
- Product
  - image
  - title
  - SKU
  - ASIN
- Status
- Supplier
  - supplier name
  - supply code
- Packs
  - short human label such as `Unit` or `Pack 3 | Case 20`
- Stock
  - on hand
  - on order
- Cost
  - current supplier price
  - last purchase price
- Demand
  - velocity 30d
  - days cover
- Profit
  - ROI snapshot
- VAT
  - rate
- Action
  - `View`
  - `Edit`

The list should be usable without opening every row.

## 4) What belongs in expansion or side detail

### Identity
- brand
- product type
- size
- dimensions
- main image

### Supply and packs
- supplier code
- supplier name
- supplier SKU
- barcode
- supplier pack size
- Amazon pack size
- MOQ
- order quantity mode
- sell pack quantity
- supplier case quantity
- supplier case multiple
- valid order step
- repack required
- bundle required
- pack conversion note

### Economics and VAT
- supplier catalog price
- last purchase price
- target margin
- VAT rate
- tax code when available
- live listing price
- last sold price
- fee and commission context where already present

### Stock and demand
- stock total
- stock available
- reserved
- inbound buckets
- ordered open quantity
- velocity 7d, 30d, 90d
- days cover

### Operations
- sale status
- O queue status
- displayed operational status
- current reorder recommendation context if useful
- snooze detail if present

### Audit
- last updated timestamps from upstream snapshots
- operator notes
- issue flags

## 5) Status model

### Displayed status values
Main badges:
- Live
- Snoozed
- Discontinued
- Dropped

Secondary non-badge issues:
- Missing pack truth
- Missing cost truth
- Missing VAT
- Missing supplier code

### Status precedence
Use one displayed `operational_status`:
1. Snoozed
2. Discontinued
3. Dropped
4. Live

Raw fields such as `sale_status` and `queue_status` should still be visible in detail.

## 6) Fixed vs derived field ownership

### Fixed editable truth
These belong on the edit page:
- supplier identity
- supplier SKU or supply code
- barcode
- sale status
- supplier pack size
- Amazon pack size
- MOQ
- order quantity mode
- sell pack quantity
- supplier case quantity
- supplier case multiple
- valid order step
- repack required
- bundle required
- pack conversion note
- supplier catalog price
- last purchase price
- target margin
- VAT rate
- notes

### Derived read-only truth
These stay off the edit form:
- stock
- open ordered quantity
- velocity
- days cover
- ROI snapshot
- live market price
- fee context

## 7) Edit page model
- Separate page or route, not inline table editing.
- Same page sections each time:
  - Product and Supplier
  - Pack and Batch Rules
  - VAT and Commercial
  - Status and Notes
- Right side or lower panel should show read-only context:
  - current stock
  - on order
  - velocity
  - ROI
  - current recommendation context

## 8) Why this is close to the finished system
- The browse page stays clean at scale.
- The detail view keeps important context close without flooding the row list.
- The edit page owns the manual fields in one place.
- The data model already supports reorder, receiving, and later audit without redesigning the page again.
