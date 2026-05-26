# O Reorder Board Blueprint

This file locks the next-stage blueprint for the O reorder board UI and row logic.

The aim is:
- modern interface
- spreadsheet density
- supplier-first workflow
- app-style interactions where useful
- no hidden important operating data

## Core Principle

The reorder board should feel like a polished operational sheet, not a tall card interface and not a generic app table.

That means:
- one compact row per product
- important fields always visible in-row
- only true actions editable
- supplier grouped sections
- modern styling and controls

## Locked Header Model

Visible row headers:

| Header | Purpose | Editable |
| --- | --- | --- |
| Img | Tiny fixed thumbnail | No |
| Supplier | Supplier grouping and ordering context | No |
| SKU | Primary lookup key | No |
| ASIN | Secondary lookup key | No |
| Name | Product name | No |
| Qtys | Pack quantity logic field | No |
| Barcode | Supplier site lookup aid | No |
| Supply Code | Supplier product code | No |
| CPU | Current unit price basis | No |
| Ordrd | Current ordered / inbound amount | No |
| Stock | Current stock | No |
| ROI | ROI at current price basis | No |
| Vlcity | Sales velocity | No |
| Days | Days cover | No |
| Recommend | Human-facing recommendation label | No |
| Restk | Suggested reorder quantity | No |
| Action | Inline action popover | Yes |
| Ordered | Final operator order quantity | Yes |
| Price | Final operator confirmed price | Yes |
| Done | Completion marker | Yes |
| Text | Optional operator text field | Yes, only if retained |
| Resk Val | Reorder value / money context | No |

## Human Language Rules

Do not show internal backend terms in the main row.

Never show:
- `full_restock`
- `test_restock`
- `UI_PREVIEW_SAMPLE`
- backend/debug/source labels

Show:
- `Restock`
- `Test`
- `No Data`
- `Wait`

Business meaning:
- `No Data` means no usable sales data and should be treated as a test candidate, not a dead row.
- `Test` means cautious reorder candidate.
- `Restock` means normal reorder candidate.
- `Wait` means do not act now.

## Action Column

Replace separate `Disc`, `Drop`, and `Snze` columns with one `Action` control.

Behavior:
- compact inline trigger in row
- opens floating top-layer popover
- does not expand row height

Popover options:
- `None`
- `Discount`
- `Drop`
- `Snooze`

If `Snooze` is selected:
- show date picker inside the popover

## Qtys Field: Locked Meaning

`Qtys` is not a simple display field.

It must describe how the product is bought, packed, and ordered in valid real-world units.

This field touches multiple dimensions:
- supplier purchase pack / case quantity
- internal repack quantity
- sell pack quantity
- valid reorder step size

So `Qtys` must be backed by structured data, not just a label.

## Quantity Model

Each SKU may need the following fields in data:

| Field | Meaning |
| --- | --- |
| `supplier_case_qty` | Units inside one supplier box/case |
| `sell_pack_qty` | Units inside one Amazon sellable pack |
| `order_multiple_sell_packs` | Valid reorder step in sellable packs |
| `supplier_case_multiple` | Whether order must align to full supplier cases |
| `repack_required` | Whether we convert supplier units into sell packs |
| `display_qtys_label` | Human-readable row text for `Qtys` |

## Example Rule: A2-T2AC-TW3L

Example business logic:

- supplier sells in boxes of `20`
- we package to Amazon as packs of `3`
- valid reorder steps are `120`, `240`, `360` sell packs

Meaning:
- `360` is the reorder quantity in sell packs
- actual unit requirement is `360 x 3 = 1080` units
- supplier boxes required = `1080 / 20 = 54`
- valid because it lands exactly on full boxes with no spare units

This means the reorder board must understand:
- the number entered in `Ordered` may represent sell packs
- supplier purchasing may need conversion to raw units and case counts
- valid values should align with both packaging and supplier constraints

## Locked Quantity Conversion Rule

When repack logic exists, the reorder system must support:

1. visible operator quantity
- default to the sellable quantity the operator thinks in

2. hidden conversion quantity
- convert operator quantity into raw units required

3. supplier validity check
- raw units must align with supplier case quantity when required

4. valid order step handling
- if a SKU can only be sensibly ordered in specific sell-pack multiples, the UI should respect that

## Recommended Data Fields For Next Stage

Add these fields to the O quantity blueprint:

| Field | Example |
| --- | --- |
| `order_qty_mode` | `sell_packs` |
| `sell_pack_qty` | `3` |
| `supplier_case_qty` | `20` |
| `valid_sell_pack_step` | `120` |
| `raw_units_per_step` | `360` |
| `supplier_cases_per_step` | `18` |
| `ordered_sell_packs` | `360` |
| `ordered_raw_units` | `1080` |
| `ordered_supplier_cases` | `54` |

## UI Rule For Quantity Editing

The reorder board should not leave this to manual maths.

Preferred behavior:
- operator edits `Ordered` in their natural working unit
- UI shows or derives valid quantity choices
- invalid values should be prevented or clearly corrected

Possible interaction:
- standard numeric input for simple SKUs
- dropdown / stepped selector for constrained SKUs

For constrained SKUs like the example above:
- entering arbitrary values should not be allowed if they break supplier/case/repack rules

## Data Interpretation Rule

Do not assume `Ordered` always means raw units.

For some SKUs it may mean:
- sell packs
- supplier cases
- raw units

So each SKU needs an explicit quantity mode.

## Table Design Direction

The reorder board should:
- keep dense row layout
- keep key lookup fields visible
- keep recommendation and quantity fields visible
- use modern styling and colour
- avoid tall rows
- avoid hidden important data in footnotes

The reorder board should not:
- rely on large cards
- hide lookup fields below the row
- expose backend wording
- require mental conversion for pack maths where the system can do it

## Next-Stage Build Requirement

Before the next major UI pass, the implementation should:

1. map each header to a real source field or explicit placeholder
2. define quantity mode per SKU
3. support constrained quantity logic for repack SKUs
4. decide whether `Text` remains a main-column field or moves into a secondary control
5. implement `Action` as a popover instead of fixed columns

## Real Operator Workflow Notes

The following notes come from the live Google Sheet workflow and should be treated as rebuild requirements, not optional ideas.

### Supplier-first workflow

The operator does not work line by line across mixed suppliers.

Actual workflow:
- open reorder list
- look at the next supplier section
- decide whether that supplier is worth dealing with right now
- process all relevant products for that supplier
- move to the next supplier

Implication:
- supplier grouping is not cosmetic, it is core workflow
- supplier-level actions matter
- supplier-level snooze is valid when the order is not worth placing yet

### Minimum worthwhile order

If a supplier only has a small value of suggested stock, the operator may snooze the supplier instead of placing a low-value order.

Example:
- DHB had only about GBP36 worth of suggested stock
- if that was a fresh list, supplier-level snooze would likely be used because the order is not worth placing

Implication:
- the system needs supplier-level value awareness
- supplier sections should show order value summary
- snooze may happen because the supplier order is too small, not because the SKU itself is bad

### Supply code is a first-class lookup field

For real ordering, the operator often uses `Supply Code` before anything else.

Typical action:
- copy supply code
- check supplier website or supplier price file
- confirm latest price
- confirm stock or backorder position

Implication:
- `Supply Code` must stay visible in the row
- it must not be hidden in a footnote or secondary detail

### Current supplier price check happens before commit

The sheet may show historical purchase logic, but the real decision uses current supplier pricing.

Actual operator behavior:
- compare latest supplier price against last purchase price
- use that as a rough first sense check
- then check current ROI against current selling conditions

Important note:
- the new system should be better than the old one here
- do not regress to backward-looking logic just to copy the old sheet

Implication:
- the rebuild must preserve forward-looking ROI logic
- current supplier price must be treated as the real buy truth when available

### No Data means test, not ignore

`No Data` in the old sheet means no sales data, not "do nothing forever".

Current operator thinking:
- if there is no data, estimate a testing level
- use BSR, current pricing, and competition levels
- test size is usually around 10 to 50 units depending on value and likely demand

Example:
- DHB product `HL-03ZR-QPHH`
- no data
- instinctive test quantity could be 10

Implication:
- `No Data` should map to a test path
- not a dead-end state
- test quantity logic should eventually use market and competition context

### Manufacturer presence affects the decision

Operator decision is not made from price alone.

Example:
- current manufacturer price meant the product would lose about GBP1.24 per unit
- manufacturer presence on the listing is a real factor
- some manufacturers like Curaprox may coexist without trouble, but this is still a decision input

Current operator leaning in this type of case:
- do not restock now
- likely discontinue for now
- allow future product scanner to retest later

Implication:
- discontinue does not mean permanent death
- the system should support "drop for now, retest later"

### Discontinue is reversible via future scanning

Current operator meaning of discontinue:
- stop active restocking now
- leave room for the future new-product scan / product scanner to rediscover and retest

Implication:
- the rebuild should treat discontinue as operationally reversible
- not as permanent deletion logic

### Supplier ordering methods differ, but system should stay generic

Current rule:
- do not customise the system per supplier in a way that requires recoding for every new supplier

Reality:
- some suppliers are checked through a latest price file
- some are checked on a website
- some allow instant ordering
- some require email and reply confirmation

Implication:
- use a generic overall system
- model supplier capabilities in data, not in hardcoded bespoke flows

### Website stock visibility changes the action

Example: Stax product `AK-OB6V-HIYD`

Observed workflow:
- open supplier website
- search by supply code `348926`
- inspect:
- current price
- discount tier
- stock position
- reserved quantity
- on-order quantity

Observed data:
- 17+ discount exists
- visible stock was effectively out
- on-order from supplier was shown

Decision:
- snooze the product for now
- because it is out of stock
- because the order can wait until stock returns

Implication:
- visible supplier stock is a real decision input
- visible supplier discount breaks are a real decision input
- stock-driven snooze is a first-class action

### Supplier confirmation may change the order after submission

For some suppliers, the initial order is not final.

Example email workflow:
- operator sends order text to supplier
- supplier replies with:
- changed price
- limited stock
- supplier issue
- partial availability

Example response pattern:
- one item unavailable due to supplier issue
- another item price changed
- only part of requested quantity available

Implication:
- placing the order request is not the final truth
- system should support a pending-confirmation stage
- final confirmed supplier response may change price and quantity

### Text column has real operational use

`Text` is not decorative in the old sheet.

Current formula:
- `=IF(S3>0,G3&" x "&S3,"")`

Meaning:
- when ordered quantity is greater than zero
- produce supplier-ready order text
- format: `SupplyCode x OrderedQty`

Usage:
- copy/paste into supplier email or supplier communication

Implication:
- if `Text` remains in the rebuild, it should serve this exact purpose
- if hidden from main row, it still needs to be easily accessible for supplier communication

### Example scenarios recorded so far

#### DHB scenario

SKU:
- `HL-03ZR-QPHH`

Observed workflow:
- supplier first
- only one product visible
- likely supplier snooze if low total order value
- use supply code against latest DHB price file
- compare latest price vs known history
- check current profitability using current market situation

Observed thinking:
- no data means possible small test
- manufacturer price made current sale unprofitable
- likely discontinue for now
- allow future scanner to retest later

#### Stax scenario

SKU:
- `AK-OB6V-HIYD`

Observed workflow:
- open Stax website
- paste supply code
- check:
- current price
- discount threshold
- stock level
- reserved qty
- on-order qty

Decision:
- product out of stock
- snooze for now
- not discarded
- no custom Stax-only logic should be baked into system code

## Rebuild Guidance From These Notes

These operator notes imply the rebuild must support:

1. supplier-first decision flow
2. supplier-level snooze/value awareness
3. visible supply code and barcode in row
4. current price checking before order commit
5. no-data test path
6. reversible discontinue logic
7. supplier capability modeling without per-supplier recoding
8. stock/delay/discount aware snooze decisions
9. pending supplier confirmation after draft order creation
10. supplier communication text generation
