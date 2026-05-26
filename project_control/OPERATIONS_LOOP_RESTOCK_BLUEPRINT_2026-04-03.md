# Operations Loop Restock Blueprint

## 1. Purpose

This document is the implementation blueprint for the first real build of the Operations Loop:

Restock Advisor -> Purchase Orders -> Ordered Stock Tracking / Receiving -> Send To Amazon

Scope of this blueprint:
- existing SKU replenishment only
- planning and data design only
- no code changes yet

This is intentionally rooted in the old Google Sheets process so we keep the useful business behavior, but it is redesigned around SellerOne local truth so we do not keep copying the same data into multiple helper sheets.

Important planning note:
- some settings in this blueprint are intentional starter settings, not permanent truths
- where real-world behavior matters more than theory, the first version should launch with a sensible default and then be tuned from evidence
- the goal is to avoid shadow-boxing every edge case before the system has real operating feedback

## 2. Plain-English Summary

The old sheet system did three useful things:
- decided which SKUs looked worth buying again
- gave a human a list to work through
- pushed approved buys into an order-tracking sheet

The new version should keep that shape, but the logic needs to be cleaner:
- demand should come from our local sales data
- stock should come from our local inventory data
- market price context should come from our local pricing data
- buying cost should come from the current supplier-side cost, not historical sold cost
- new data should only be created for genuinely new states like recommendation, approval, PO, receiving, and send-to-Amazon handoff

Core design rule:
- Restock must consume existing A/B/E/H outputs wherever those outputs already exist.
- Restock must not create local copies of A/B/E/H truth just to make the script easier.
- New restock-owned files are allowed only where they represent brand-new workflow state that does not exist today.

## 3. What The Old Google Sheets System Actually Did

## 3.1 Main reference files reviewed

- `reference/Restocking References/google sheet pages/1H_EDAYfB_xgGvnW1esOMwWsHs2wBXYoOABcMs7SWcrY/scripts.gs`
- `reference/Restocking References/google sheet pages/1F4he4z06NppO7fWhsQ-NKCYxIxokxt16Gj09x1d0lR0/scripts.gs`
- CSV exports from the same folders for Product Database, Purchase List, Orders, ROI Data, and Stock Data

## 3.2 Legacy flow shape

### Step A - Import Sellerboard stock email

The old `importStockReport()` Apps Script:
- read CSV attachments from Gmail
- appended rows into `ROI Data`
- appended rows into `Stock Data`

That produced a growing history table rather than one clean current-state table.

### Step B - Update Product Database helper columns

The old `updateProductDatabaseKU()` script:
- opened `Product Database`
- joined in `ROI Data`
- joined in `Stock Data`
- joined in `Orders`
- filled columns `K` to `U`

Those helper columns then drove the restock suggestion.

### Step C - Build Purchase List

The old `copyProductData()` script:
- filtered Product Database rows where restock qty was above zero
- copied selected columns into `Purchase List`
- added formulas and checkboxes
- sorted by supplier

This produced the working buy list for a human.

### Step D - Human decisions and order logging

The old `processDoneTicksAndDelete()` script:
- used checkboxes for discard / drop / snooze / done
- when done was ticked, copied the SKU, ordered qty, price, and date into `Orders`
- deleted the completed row from `Purchase List`

That means the old system mixed:
- recommendation
- human decision
- buy execution
- history cleanup

inside the same working sheet.

### Step E - Token logging

The old `runTokenLogger()` script:
- watched the `Orders` sheet
- compared `Sent to FBA` against a snapshot
- appended token rows when that quantity increased

That was a rough bridge from buying workflow into token tracking.

## 4. Main Problems In The Old System

These are the key reasons we should not rebuild it like-for-like.

### 4.1 Too many copied layers

The old system copied the same business facts across:
- Product Database
- Purchase List
- Orders
- ROI Data
- Stock Data
- Snapshot

That makes it hard to know which layer is the truth.

### 4.2 Historical ROI was used for a forward buy decision

This is the big business issue you called out.

The old flow was effectively using past sales economics to justify a future buy.

That breaks when:
- supplier price changes
- fees shift
- market price drops
- refund behavior changes

Restock must instead answer:
- "If we buy this again now, at the current buy price, does it still clear our rules?"

### 4.3 The legacy script appears to misuse one source field

In the old sheet script, `ROI Data` is imported as:
- timestamp
- ASIN
- SKU
- ROI percent
- estimated sales velocity

But `updateProductDatabaseKU()` reads columns `C:D:E` from that sheet and treats them as:
- SKU
- ROI
- cost

That means the script appears to use estimated sales velocity in the slot it calls `cost`.

This is a strong reason not to inherit the old formula logic.

### 4.4 Stock buckets are blended in a rough way

The old script maps stock columns into `O:P:Q:R` and then sums them into reorder logic.

That logic:
- duplicates one bucket
- mixes physically different stock states together
- does not clearly separate on-hand stock from inbound stock

The new design must keep stock states explicit.

### 4.5 Recommendation state and workflow state are mixed together

The old sheets use the same rows for:
- suggested reorder qty
- decision status
- snooze flag
- ordered qty
- done flag

That is workable in a small sheet, but it is the wrong structure for a local loop we want to trust later.

## 5. What SellerOne Already Has That We Can Reuse

## 5.1 Existing local data sources with clear value for restock

### A-owned stock state

Primary local stock snapshot:
- `out/inventory_summaries.csv`

Useful columns already present:
- `seller_sku`
- `asin`
- `total_quantity`
- `available`
- `reserved_quantity`
- `inbound_working`
- `inbound_shipped`
- `inbound_receiving`

Use:
- current Amazon-side stock position
- stock coverage calculation
- inbound visibility

### B-owned sales and finance base

Primary local order/economics base:
- `out/order_master.csv`

Use:
- sold units
- actual revenue
- actual COGS history
- actual fee history
- country split if needed

### E-owned demand signal

Current velocity output:
- `out/sku_sales_velocity.csv`

Use:
- 7/30/90-day demand rates
- latest order window
- current days-in-stock estimate basis

### E-owned realized ROI signal

Current ROI snapshot:
- `out/sku_roi_snapshot.csv`
- `out/sku_roi_snapshot_by_country.csv`

Use:
- realized trailing profitability context
- diagnostics

Do not use as the main restock gate for current-buy decisions.

### E-owned simple restock signal

Current output:
- `out/sku_restock_signals.csv`

Use:
- proof that the repo already has a simple reorder layer
- starting point only

Current limitation:
- it only uses velocity and available stock
- it does not solve current-buy-price ROI
- it does not include supplier-side workflow state

### E-owned merged performance table

Current output:
- `out/sku_performance_summary.csv`

This is already the strongest single analytics table for restock planning because it merges:
- velocity
- realized ROI snapshot
- simple restock signal
- current token cost estimate
- break-even estimate
- expected refund drag
- ROI at our current market price
- ROI at buy box / market price
- value velocity

Important note:
- the current projected ROI fields are still based on token-cost-style history, not the current supplier buy cost for a fresh restock decision

### H-owned market price context

Current price inputs used by E/H:
- `out/listing_offer_snapshot_latest.csv` or latest dated snapshot
- `out/listing_offer_history.csv`

Use:
- latest our live price
- latest buy box price
- latest lowest FBA price

### Current supplier-side item data

Current local convenience source:
- `out/product_db_preview.csv`

Useful fields already present:
- `seller_sku`
- `asin`
- `supplier_code`
- `supplier_name`
- `supplier_pack_size`
- `supplier_catalog_price`
- `last_purchase_price`
- `sale_status`
- `vat_rate`
- fee fields

Important note:
- this file is currently a local snapshot of sheet-backed product data, not a clean owner-native master
- but it is still the best current local source for supplier-side cost and supplier metadata

## 5.2 Existing local data we should not duplicate

The restock build should consume, not re-copy:
- `out/inventory_summaries.csv`
- `out/order_master.csv`
- `out/sku_sales_velocity.csv`
- `out/sku_performance_summary.csv`
- `out/product_db_preview.csv`
- inbound status outputs when later loop stages need them

## 6. Single-Source Rule For The New Restock Design

Each fact used by restock should have one authority source inside the implementation.

Recommended source map:

| Decision fact | Recommended source | Notes |
|---|---|---|
| SKU identity | `out/product_db_preview.csv` | Interim source until supplier/item master is separated cleanly |
| Supplier / supplier code | `out/product_db_preview.csv` | Do not copy into a parallel reference table |
| Current supplier buy cost | `out/product_db_preview.csv` | Prefer `supplier_catalog_price`, fallback `last_purchase_price` |
| Amazon stock now | `out/inventory_summaries.csv` | Source for available and total quantity |
| Amazon inbound stock | `out/inventory_summaries.csv` | Keep inbound buckets separate |
| Sales velocity | `out/sku_sales_velocity.csv` | Use E-owned output |
| Market price now | H snapshots/history via `sku_performance_summary.csv` or direct H source | Prefer one merged source later |
| Refund drag | `out/sku_performance_summary.csv` | Reuse analytics already built |
| Realized profitability context | `out/sku_performance_summary.csv` / `out/sku_roi_snapshot.csv` | Context only, not the main buy gate |
| Human approval outcome | new O-owned workflow file | This state does not exist today |
| PO / ordered state | new O-owned workflow file | This state does not exist today |
| Receiving state | new O-owned workflow file plus inbound evidence | New workflow state |
| Send-to-Amazon state | new O-owned workflow file plus A/B/C evidence | New workflow state |

Rule:
- if the data already exists in A/B/E/H, read it there
- if the data is a new operations-loop state, create exactly one new O-owned table for it

## 7. Recommended Flow Letter

Recommended new letter path:
- `O` for Operations Loop

Reason:
- the roadmap already treats restock as the first stage of one larger operations loop
- if we name the flow `R`, we will likely box ourselves in when Purchase Orders, Receiving, and Send To Amazon are added
- `O` gives one clean family for the full chain:
  - `scripts/flows/O/`
  - `out/systems/O/live/`

Recommended staging inside `O`:
- `O001` to `O099` - Restock Advisor
- `O100` to `O199` - Purchase Orders
- `O200` to `O299` - Ordered stock / Receiving
- `O300` to `O399` - Send To Amazon

## 8. Recommended Architecture

## 8.1 Core design idea

Separate the loop into two kinds of data:

### Existing truth we read

This comes from A/B/E/H and should stay there:
- stock
- demand
- market prices
- historical performance
- token cost history

### New workflow truth we own

This belongs to the Operations Loop and does not exist anywhere else today:
- recommendation rows
- decision status
- approved restock quantity
- PO records
- supplier order status
- receiving events
- send-to-Amazon handoff records

## 8.2 Restock should not be a spreadsheet clone

The new system should not recreate:
- formula columns
- checkbox-driven delete loops
- helper tabs that only exist to hold copied values

Instead it should work as:
1. build recommendation dataset
2. build human review dataset
3. apply decision into one append-only decision log
4. promote approved decisions into PO state
5. keep PO / receiving / send state as explicit datasets

## 9. Proposed Restock Decision Model

## 9.1 Restock question

For each active SKU, the system should answer:

- Do we need more units soon?
- If yes, can we buy them now at the current supplier cost and still hit the economics rule?
- If yes, how many units should we buy?
- If no, why not?

## 9.2 Inputs for the decision

### Demand input

Use E velocity.

Recommended initial behavior:
- primary demand rate = `v30`
- supporting context = `v7`, `v90`
- later improvement = blended velocity with guardrails for sudden spikes

### Stock input

Use A inventory summary.

Recommended stock buckets:
- `available_now`
- `reserved_now`
- `amazon_inbound_working`
- `amazon_inbound_shipped`
- `amazon_inbound_receiving`
- `supplier_ordered_not_yet_arrived` from future O-owned PO state

Do not flatten these into one hidden formula.

### Buy-cost input

This is the business-critical change.

Recommended initial rule:
- current buy cost = `supplier_catalog_price`
- fallback = `last_purchase_price`
- if neither exists, recommendation status = blocked for missing current buy cost

Do not use:
- trailing sold COGS
- token cost
- old realized ROI

as the buy-cost gate for a new restock order.

### Sell-price input

Use current market context.

Recommended initial fields:
- `our_live_price_gbp`
- `buy_box_price_gbp`
- `lowest_fba_price_gbp`

Conservative gate:
- use buy box price if available
- else use lowest FBA
- else use our live price

### Economics input

Needed per-SKU inputs:
- current supplier buy cost
- estimated fee drag
- estimated refund drag
- current market sale price

Output we actually want:
- forward profit per unit at current market price
- forward ROI at current market price

This is the calculation that fixes the old system.

## 9.3 Initial recommendation logic

Recommended first-pass logic:

1. Eligibility
- SKU is active
- not explicitly discontinued
- has usable supplier and cost data

2. Demand
- velocity above a minimum floor or recent sales present

3. Stock pressure
- days of cover at current demand is below threshold

4. Forward economics
- ROI at current market price is above threshold

5. Quantity suggestion
- target cover days minus current and inbound supply
- rounded to pack size and MOQ rules

6. Recommendation label
- `buy_now`
- `watch`
- `blocked_missing_cost`
- `blocked_bad_economics`
- `blocked_no_demand`
- `snoozed`
- `drop_candidate`

## 9.4 Quantity formula direction

Recommended formula shape:

`target_units = target_days_of_cover * daily_velocity`

`net_needed = target_units - effective_supply`

Where:
- `effective_supply` includes available stock plus appropriate inbound/ordered states
- ordered stock must come from O-owned PO state once that exists
- final qty should then respect:
  - MOQ
  - supplier pack size
  - optional max-cap guardrails

Locked planning rule:
- anything already ordered should count as stock in the pipeline
- default target cover is `30 days`
- supplier-aware target cover may increase above `30 days` when slower supplier lead times, minimum delivery charges, or ordering friction justify it
- supplier-aware target cover may go as high as `90 days` where commercially sensible and capital use remains acceptable

## 10. Recommended Data Products

## 10.1 Reuse and strengthen existing E output

Best design:
- keep `out/sku_performance_summary.csv` as the main merged analytics table
- later extend it with explicit current-buy-cost restock economics fields

Recommended new columns to add there later:
- `current_supplier_buy_cost_gbp`
- `current_supplier_cost_source`
- `forward_profit_at_market_price_gbp`
- `forward_roi_at_market_price_pct`
- `forward_profit_at_our_price_gbp`
- `forward_roi_at_our_price_pct`
- `forward_price_basis_used`

Reason:
- this avoids creating a second copied analytics table
- O can consume one merged performance source
- names stay explicit so historical ROI and forward ROI do not get confused

## 10.2 New O-owned workflow datasets

These are justified because they represent brand-new workflow state.

Recommended live files:

### `out/systems/O/live/restock_recommendations_live.csv`

One row per SKU per build snapshot.

Suggested fields:
- `asof_utc`
- `seller_sku`
- `asin`
- `supplier_code`
- `supplier_name`
- `sale_status`
- `available_now`
- `reserved_now`
- `amazon_inbound_working`
- `amazon_inbound_shipped`
- `amazon_inbound_receiving`
- `supplier_ordered_open_qty`
- `velocity_7d`
- `velocity_30d`
- `velocity_90d`
- `days_cover_available_only`
- `days_cover_total_pipeline`
- `current_supplier_buy_cost_gbp`
- `current_supplier_cost_source`
- `market_price_gbp`
- `market_price_basis_used`
- `forward_roi_pct`
- `forward_profit_per_unit_gbp`
- `target_days_cover`
- `recommended_qty_raw`
- `recommended_qty_rounded`
- `recommendation_status`
- `reason_codes`

Plain-English purpose:
- this is the system's current opinion
- one row per SKU
- answers "what do we think we should do right now, and why?"

### `out/systems/O/live/restock_decisions_log.csv`

Append-only human decision log.

Suggested fields:
- `decision_utc`
- `seller_sku`
- `decision_status`
- `decision_qty`
- `decision_price_gbp`
- `decision_reason`
- `operator`
- `recommendation_asof_utc`
- `snooze_until_utc`

Plain-English purpose:
- this is the human action log
- answers "what did we actually choose to do?"
- must be append-only so later review is honest

User-confirmation rule:
- the system may pre-fill suggested order quantity and suggested unit price
- the user must confirm the final unit price before the order is committed
- if the user corrects the price, that corrected price becomes the committed buy-cost truth for that order

### `out/systems/O/live/restock_review_log.csv`

Append-only outcome review log.

Suggested fields:
- `review_utc`
- `seller_sku`
- `decision_utc`
- `original_recommendation_status`
- `actual_decision_status`
- `decision_qty`
- `days_until_first_sale`
- `units_sold_30d_after_decision`
- `units_sold_60d_after_decision`
- `realised_profit_gbp`
- `realised_roi_pct`
- `stock_age_days`
- `price_strength_result`
- `outcome_grade`
- `review_notes`

Plain-English purpose:
- this is the report card
- answers "did that decision turn out to be a good one?"
- this is the piece that lets the system improve instead of staying guesswork forever

### `out/systems/O/live/purchase_orders_live.csv`

Header-level PO state.

Suggested fields:
- `po_id`
- `created_utc`
- `supplier_code`
- `supplier_name`
- `po_status`
- `currency`
- `total_lines`
- `total_units`
- `total_value_gbp`
- `approved_from_decision_batch`

### `out/systems/O/live/purchase_order_lines_live.csv`

Line-level PO truth.

Suggested fields:
- `po_id`
- `seller_sku`
- `asin`
- `ordered_qty`
- `ordered_unit_cost_gbp`
- `supplier_pack_size`
- `moq`
- `expected_arrival_utc`
- `receipt_status`
- `received_qty`
- `remaining_open_qty`

### `out/systems/O/live/receiving_events.csv`

Append-only receiving log.

Suggested fields:
- `event_utc`
- `po_id`
- `seller_sku`
- `received_qty`
- `warehouse_ref`
- `event_source`

### `out/systems/O/live/send_to_amazon_queue.csv`

Queue for units ready to move into the Amazon inbound step.

Suggested fields:
- `queue_utc`
- `po_id`
- `seller_sku`
- `received_qty_available_for_send`
- `send_status`
- `shipment_ref`

## 10.3 Minimum 3-table learning loop

If we want the system to improve over time, the restock part needs these three tables at minimum:

### 1. Recommendation table

This is what the system thinks before any human step.

It should contain:
- the current facts
- the suggested action
- the reason

Simple example outputs:
- `full_restock`
- `test_restock`
- `wait`

### 2. Decision log

This is what actually happened after review.

It should contain:
- what the system recommended
- what the human chose
- what quantity was approved

This matters because if the human overrides the system, we still want to know what the original system call was.

### 3. Review log

This is the later scorecard.

It should contain:
- what we expected
- what we actually did
- what actually happened later

This is how we tell whether the rule set is working.

Without this third table, the system can produce recommendations but it cannot learn whether they were good recommendations.

## 10.3A Assumption -> user confirmation -> path suggestion

This is the recommended v1 buying pattern.

### Step 1 - System assumption

The system prepares the order suggestion using the best local information available at the time:
- suggested quantity
- suggested unit cost
- suggested path
- expected forward ROI

### Step 2 - User confirmation

Before any order is committed, the user confirms:
- final quantity
- final unit price actually being paid

This matters because supplier prices can change at the point of ordering.

### Step 3 - Final path suggestion

After the price is confirmed, the system should immediately recalculate:
- forward ROI
- path result
- downgrade or fail warning if the economics weaken

Recommended behavior:
- if the corrected price pushes a SKU from `full_restock` into `test_restock`, show a clear downgrade
- if the corrected price pushes a SKU below the `10%` floor, show a clear warning that it no longer meets the minimum rule
- the system should never silently keep the old recommendation after price correction

Recommended v1 fallback:
- if no clean live supplier cost exists, the user can act as the final price source at order time
- this is acceptable for v1 because the confirmed price is saved as the committed buy truth for that decision

### Date-based snooze

Recommended rule:
- snooze should be date-based, not just on/off
- the user should be able to choose a specific future date
- until that date is reached, the product should not be surfaced again as an active recommendation

Plain-English examples:
- supplier expects stock end of June
- user snoozes to that date
- product stays out of the active review queue until then

Planning rule:
- snooze should hide repeated suggestion noise
- it should not delete the product or its history
- once the snooze date is reached, the SKU becomes eligible for review again

## 10.4 Simple first version of the score

The first version should stay simple.

Recommended first-pass recommendation labels:
- `full_restock`
- `test_restock`
- `wait`

Recommended starter rule set:
- `full_restock target_days_cover = 30`
- `test_restock target_days_cover = 10`
- `minimum forward ROI = 10%`
- `strong forward ROI for full restock = 15%`
- `max test spend per SKU = GBP 150`

Recommended meaning:

### `full_restock`
- demand is healthy
- stock pressure is real
- current buy cost still works against current market price
- confidence is high enough to buy normal quantity

Suggested first-pass gate:
- forward ROI is `15% or higher`
- buy to `30 days` cover

### Middle band rule

Suggested first-pass gate:
- if forward ROI is between `10%` and `15%`
- do not allow a full restock yet
- allow `test_restock` only

### `test_restock`
- demand exists
- but margin, price stability, or confidence is weak
- so we buy a smaller amount to test the market instead of taking full exposure

Suggested first-pass gate:
- forward ROI is between `10%` and `15%`
- buy to `10 days` cover
- cap total test spend at `GBP 150`
- then apply MOQ and pack-size rounding

### `wait`
- demand may exist, but the item does not currently justify a buy
- this is not the same as permanent drop
- it means "not now at this cost and this price picture"

Suggested first-pass gate:
- forward ROI is below `10%`
- or current market price picture is too weak
- or demand is too weak to justify a buy

Important planning rule:
- strong demand on its own should not force a `full_restock` through the middle band
- in the `10% to 15%` ROI zone, the safer starting rule is `test_restock` only

Tuning note:
- these thresholds are first-pass operating settings
- they should be reviewed after live use and adjusted if the review log shows the system is too aggressive or too conservative

## 10.5 How to tell later if the system is working

We should not judge the system by asking whether every single SKU call was perfect.

We should judge it by whether the decision groups behave well over time.

Recommended review questions:
- do `full_restock` items actually produce healthy realised ROI?
- do `test_restock` items protect cash while still catching recoveries?
- do `wait` decisions avoid bad buys more often than they miss good buys?
- are too many full restocks turning into slow stock?
- are too many waits turning into missed easy winners?

Recommended first-pass outcome grades:
- `good`
- `mixed`
- `bad`

Simple meaning:
- `good` = outcome broadly matched the recommendation
- `mixed` = some parts worked, but the decision size or timing could be better
- `bad` = the decision was clearly wrong or too aggressive

## 10.6 What success looks like at portfolio level

When we are managing hundreds of products, the system is working if it improves the portfolio, not just a few cherry-picked examples.

So the review layer should later let us compare:
- full restock success rate
- test restock success rate
- wait accuracy
- cash tied up
- average realised ROI after decision
- slow-stock creation rate
- missed-opportunity rate

That is the evidence loop.

The system makes a call, we act, then we grade the result and tune the rules from evidence rather than instinct.

## 11. What Should Be Reused Vs What Should Be Replaced

## 11.1 Keep from the old process

- supplier-grouped buy view
- clear human approval step before commitment
- ability to snooze / watch / drop a SKU
- ability to move an approved recommendation into buying workflow

## 11.2 Replace from the old process

- sheet formulas as business logic
- copied helper tables
- checkbox state as durable system state
- delete-row-as-history behavior
- historical ROI as the main future-buy gate

## 12. Specific Improvement Over The Current Local E Restock Layer

Current `E003_build_restock_signals.py` is useful but too small for the real loop.

It currently does:
- days of stock left from `available / velocity`
- simple reorder flag
- simple reorder qty toward 30 days

It does not do:
- current supplier buy-cost gating
- forward ROI gating
- supplier pack / MOQ rounding
- ordered-but-not-yet-received state
- human approval state
- purchase order lifecycle

Blueprint decision:
- keep E003 as a lightweight analytics signal if desired
- do not treat E003 output as the final restock decision engine

## 13. Recommended Build Order

## 13.1 Phase 1 - Restock Advisor only

Future scripts:
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O002_build_restock_recommendations.py`
- `scripts/flows/O/O003_build_restock_review_queue.py`

Outcome:
- one clean recommendation table
- one human-readable review queue
- no purchase order execution yet

## 13.2 Phase 2 - Decision capture

Future scripts:
- `scripts/flows/O/O010_apply_restock_decisions.py`

Outcome:
- append-only decision log
- recommendation rows do not get deleted

## 13.3 Phase 3 - Purchase Orders

Future scripts:
- `scripts/flows/O/O100_build_purchase_orders.py`
- `scripts/flows/O/O110_publish_purchase_order_view.py`

Outcome:
- approved restocks become formal PO state

## 13.4 Phase 4 - Ordered stock / receiving

Future scripts:
- `scripts/flows/O/O200_build_ordered_stock_state.py`
- `scripts/flows/O/O210_apply_receiving_events.py`

Outcome:
- supplier-ordered stock becomes visible before Amazon receives it

## 13.5 Phase 5 - Send To Amazon handoff

Future scripts:
- `scripts/flows/O/O300_build_send_to_amazon_queue.py`
- `scripts/flows/O/O310_close_send_to_amazon_handoff.py`

Outcome:
- received stock moves cleanly into the Amazon inbound side

## 14. Critical Open Gaps To Solve During Implementation

These are not blockers for the blueprint. They are the things implementation must handle explicitly.

### 14.1 Current supplier cost authority is not fully clean

Today the best available local source appears to be `out/product_db_preview.csv`.

That is workable for v1, but long term we should aim for one cleaner supplier/item master.

## 14.1A Locked supplier-source direction

Supplier truth should be handled like this:

- each supplier may have a different intake method
- but every supplier must be converted into one standard local format before restock uses it

Allowed intake methods:
- supplier API
- supplier website scraping
- supplier CSV download
- supplier CSV by email
- other supplier-specific import methods if needed later

Locked planning rule:
- restock must not contain supplier-specific logic for every supplier
- supplier-specific collection happens upstream
- restock only reads one normalized supplier dataset

Plain-English meaning:
- every messy supplier source gets cleaned up first
- then the restock system reads one consistent local table
- this lets us add suppliers one by one later without rewriting the restock engine each time

Recommended future normalized supplier fields:
- `supplier_code`
- `supplier_name`
- `supplier_sku`
- `seller_sku`
- `asin`
- `current_unit_cost`
- `currency`
- `supplier_stock`
- `moq`
- `pack_size`
- `price_break_info`
- `availability_status`
- `source_type`
- `source_reference`
- `captured_at_utc`
- `is_current`

Recommended planning rule for v1:
- until the normalized supplier dataset exists, use current product-side supplier cost fields as the interim source
- once the normalized supplier dataset exists, it becomes the primary source for current buy cost and supplier stock

## 14.1B Locked minimum supplier schema for v1

To keep the first build practical, the normalized supplier layer should separate:
- mandatory fields
- strongly useful fields
- optional fields

### Mandatory for v1

These are the minimum fields needed for restock to work safely:
- `supplier_name`
- `supplier_sku`
- `seller_sku`
- `current_unit_cost`
- `currency`
- `captured_at_utc`

Plain-English meaning:
- who the supplier is
- which supplier item it is
- which of our SKUs it maps to
- what it costs now
- what currency that cost is in
- when we captured that price

### Strongly useful for v1

These are not absolute blockers for every supplier, but they should be included wherever possible:
- `supplier_stock`
- `moq`
- `pack_size`
- `availability_status`
- `source_type`

Plain-English meaning:
- can we buy it
- what is the minimum sensible order
- what quantity rules apply
- is it actually available
- where did this data come from

### Optional for later improvement

These should be allowed in the format, but they do not need to block the first restock version:
- `price_break_info`
- `source_reference`
- `supplier_code`
- `asin`
- `is_current`

Planning rule:
- missing mandatory fields should block that supplier row from driving automatic restock economics
- missing strongly useful fields should not always block the row, but they should reduce confidence and force simpler behavior

## 14.1F Supplier profile rules

Supplier-level commercial rules should be stored in a separate supplier profile layer and used by the restock system.

Plain-English meaning:
- some decisions are not just about the product
- they are also about how that supplier works

Recommended supplier profile fields:
- `supplier_name`
- `supplier_code`
- `moq_default`
- `can_backorder`
- `shipping_charge_rule`
- `free_shipping_threshold`
- `lead_time_profile_type`
- `bulk_discount_available`
- `order_friction_level`

Plain-English examples:
- minimum order quantity
- whether we can place a backorder or not
- shipping cost rules
- free shipping above a certain order size
- whether the supplier is generally slow
- whether the supplier tends to reward larger buys

Planning rule:
- supplier profile rules should be factored into the recommendation
- do not evaluate product profitability in isolation if supplier shipping rules could push the order into loss

Commercial effect rule:
- if a product looks profitable before shipping but unprofitable after realistic shipping cost, the system should reflect that
- if increasing order size would reasonably move the order to better shipping economics or free shipping, the system may suggest that as part of the review
- this should still be balanced against capital risk and overstock risk

## 14.1C Supplier lead time and stockout-noise rule

Lead time should be part of the restock plan.

Plain-English meaning:
- if a supplier usually takes 2 weeks to deliver
- the system should not pretend those 2 weeks do not exist

Recommended planning rule:
- maintain an average supplier lead time from history where history exists
- use that lead time to increase target cover when needed

Simple first-pass shape:
- `effective_target_days = cover_days + supplier_lead_time_days`

Example:
- normal cover target = `30 days`
- average supplier lead time = `14 days`
- planning target becomes roughly `44 days`

This should still sit inside the supplier-aware cap:
- default target around `30 days`
- supplier-aware extension allowed up to `90 days`

### Handling stockout noise

This is important because stockouts can distort the numbers.

Problem:
- if an item was out of stock, low sales during that period do not mean low demand
- equally, a short rebound after stock returns should not automatically be treated as the new normal forever

Recommended planning rule:
- demand should be measured using in-stock selling periods where possible
- out-of-stock days should not be treated as true low-demand days
- the system should prefer velocity measures that already account for actual selling windows rather than blindly dividing by the whole calendar period

Practical v1 direction:
- use existing E velocity as the starting demand signal
- improve later by excluding known out-of-stock periods from the demand denominator
- where stockout distortion is obvious, reduce confidence and prefer `test_restock` over aggressive `full_restock`

Plain-English fallback:
- if the system is not sure whether the demand number is trustworthy because stockouts muddied the picture, it should become more cautious, not more aggressive

### Lead-time history direction

Recommended rule:
- when an order is placed, record the order timestamp
- when stock arrives, record the arrival timestamp
- use those records to learn real lead time from history

Recommended split:
- keep `in-stock lead time` separate from `backorder lead time`
- do not blend them into one single average

Example:
- if a supplier item is usually in stock and arrives in `3 days`, use that pattern when it is currently in stock
- if the same item is backordered and takes `4 weeks`, use that pattern only when it is currently backordered

Planning rule:
- if supplier stock visibility exists, choose the lead-time pattern that matches the current supplier stock state
- if supplier stock visibility does not exist, use the most relevant history available rather than assuming worst case

Tuning note:
- the exact lead-time calculation method should be treated as adjustable
- use a sensible starting method in v1, then refine it from actual supplier behavior

### History-based planning, not worst-case planning

Locked planning rule:
- do not plan every SKU using its worst historical delay
- use normal historical behavior unless there is a good reason to believe current conditions are worse

Plain-English meaning:
- one bad delay should not make the system permanently over-order
- the system should be cautious, but not paranoid

Recommended order of trust:
- SKU-level history first
- supplier-level history second
- cautious fallback only when history is weak or mixed

## 14.1D Bulk, long-lead, MOQ-heavy products

Some products should not be treated like normal restocks.

Example behavior:
- large bulk buy
- discount only at high quantity
- long supplier wait
- special-order or backorder behavior
- significant capital exposure

These products need their own planning treatment because waiting until stock is simply "low" is often already too late.

Recommended classification:
- add a product-level planning flag for `bulk_long_lead`

Plain-English meaning:
- this item may need an earlier reorder point than normal
- the system should think about capital timing, not just simple monthly demand

Recommended planning rule:
- for `bulk_long_lead` items, create an earlier reorder trigger based on:
  - expected sales speed
  - lead time
  - safety buffer
  - MOQ or bulk threshold
  - capital exposure

Plain-English question the system should ask:
- "If we do not order now, are we likely to run out before the next realistic batch arrives?"

If yes:
- the item should move into an earlier reorder decision even if it still has meaningful stock left

Capital-risk rule:
- for bulk-long-lead items, the system should not only ask "will it sell?"
- it should also ask "does this order create too much stock exposure if demand softens?"

Planning consequence:
- these items should usually be reviewed with stricter human attention
- they are not good candidates for naive automatic full-restock logic

### Bulk discount review option

Some strong products may justify a separate bulk-buy review before the final restock decision is made.

Plain-English meaning:
- if a product has strong proven demand
- and a larger order could unlock a meaningfully better unit cost
- the system should be able to ask for a bulk-price check instead of only using the normal supplier price

Recommended special path:
- `bulk_discount_review`

When this path is triggered, the user should be asked to:
- find or confirm the best available bulk price
- enter the quoted bulk unit cost

Then the system should:
- recalculate the economics using that bulk price
- compare the normal buy option vs the bulk-buy option
- use the better commercial result as part of the final decision

Recommended trigger ideas:
- product has strong proven sales history
- product is approaching reorder point
- supplier offers better unit pricing at meaningful quantity breaks
- capital exposure is still within an acceptable range

Planning rule:
- this should be an option for strong products, not a blanket rule for all products
- the goal is to improve margin on proven winners, not to force oversized buys on uncertain products

## 14.1E Out-of-stock demand confidence rule

Products that have been out of stock for a while should not be treated the same as products with fresh live sales.

Problem:
- once a SKU has been out of stock for long enough, simple recent-sales windows stop being trustworthy
- old demand may still be useful
- but the selling environment may have changed since the last in-stock period

Recommended planning rule:
- when a SKU has been out of stock for a meaningful period, switch from a normal demand estimate to a confidence-based demand estimate

Plain-English meaning:
- past sales are still a clue
- but the system should trust them less as the out-of-stock gap gets longer

### What should affect confidence

Recommended comparison points between the last healthy selling period and now:
- sales rank then vs now
- buy box win rate then vs now
- seller count then vs now
- market price environment then vs now

These factors can change demand expectations in either direction.

Examples:
- if rank worsened a lot and more sellers appeared, trust old sales less
- if the listing only became weak because the next offer was unattractive, demand may recover when we return with a better offer

### Planning behavior

Recommended v1 behavior:
- if out-of-stock time is short, use normal history with high confidence
- if out-of-stock time is moderate, reduce confidence and lean toward `test_restock`
- if out-of-stock time is long and the market picture changed a lot, use a cautious assumption and prefer `test_restock` or `wait`

Locked planning rule:
- do not assume an old sales rate is still fully true after a long stockout
- do not assume old sales are worthless either
- treat old sales as a clue, then let the next restock cycle re-test the real market

### Stale-history concept

Recommended v1 concept:
- after enough days out of stock, mark historical demand as `stale`
- stale does not mean unusable
- it means confidence is reduced and the system should become more cautious

Practical v1 direction:
- stale-demand SKUs should usually not jump straight into aggressive `full_restock`
- stale-demand SKUs should more often fall into:
  - `test_restock`
  - or `wait` if the economics are also weak

Tuning note:
- the exact boundary for when demand becomes `stale` should be treated as a live-tuning setting
- do not overfit this before the first real operating cycle gives evidence

Plain-English summary:
- make soft assumptions, not hard assumptions
- then let fresh live selling after restock prove whether demand is still really there

### 14.2 Supplier currency is not obvious in the current local fields

If supplier costs can be non-GBP, the build must add:
- supplier currency
- FX conversion rule

before enabling those SKUs for automatic economics.

### 14.3 Forward ROI should be clearly separated from realized ROI

The naming in future outputs must make this impossible to confuse.

Use both concepts, but keep them explicit:
- realized trailing ROI
- forward current-buy ROI

### 14.4 Ordered stock state does not yet exist as a local operations truth

That is a valid new data product because it is new workflow state, not a duplicate of A/B/E/H.

## 15. Recommended Acceptance Standard For The Blueprinted Build

The first implementation pass should be considered structurally correct when it can do all of this:

- build a restock recommendation for active SKUs from local truth
- show which exact source supplied each major decision field
- use current supplier buy cost, not historical sold cost, for the buy decision
- separate recommendation from decision history
- create a formal promotion path from approved recommendation into PO state
- avoid new duplicate copies of A/B/E/H data

## 15.1 Useful reuse from AMZ Manager 1

The old `reference/Reference only/AMZ Manager 1` system contains useful ideas for the new operations loop.

These should be treated as reuse candidates, not copied blindly.

### Worth reusing for the new loop

#### PO stage structure

Useful reference:
- `reference/Reference only/AMZ Manager 1/ui/po_builder.py`
- `reference/Reference only/AMZ Manager 1/services/po_flow_service.py`

What is useful:
- staged PO flow
- order draft
- supplier confirmation
- receiving
- invoice
- complete

Why it matters:
- this matches the shape the new operations loop needs after Restock Advisor

#### Supplier commercial rules

Useful reference:
- `reference/Reference only/AMZ Manager 1/ui/po_builder.py`

What is useful:
- shipping tiers
- free shipping thresholds
- MOQ-aware thinking
- outstanding supplier orders by SKU

Why it matters:
- the new restock system should not judge a product in isolation if supplier shipping rules change the economics

#### Backorder handling

Useful reference:
- `reference/Reference only/AMZ Manager 1/services/po_flow_service.py`
- `reference/Reference only/AMZ Manager 1/ui/orders_by_po.py`

What is useful:
- explicit backorder vs cancel handling

Why it matters:
- the new supplier profile model already assumes some suppliers allow backorders and some do not

#### PO overdue and expected-date thinking

Useful reference:
- `reference/Reference only/AMZ Manager 1/services/po_alert_service.py`

What is useful:
- expected-date tracking
- overdue receipt tracking

Why it matters:
- this fits directly with date-based snooze, supplier wait windows, and lead-time learning

#### Amazon inbound state model

Useful reference:
- `reference/Reference only/AMZ Manager 1/docs/fba_inbound_state.md`
- `reference/Reference only/AMZ Manager 1/docs/fba_integration.md`
- `reference/Reference only/AMZ Manager 1/docs/fba_shipment_workflow.md`

What is useful:
- clear shipment states
- clear plan states
- idempotent operations
- local persistence of Amazon shipment progress

Why it matters:
- this is the right kind of thinking for the later `Send To Amazon` stage
- especially where API calls must happen in the correct order

#### Receiving queue and stock release

Useful reference:
- `reference/Reference only/AMZ Manager 1/services/fba_receiving_importer.py`
- `reference/Reference only/AMZ Manager 1/docs/fba_sync_job.md`

What is useful:
- shipment delivery queue
- delayed receiving confirmation
- releasing reservations only once the shipment is properly processed

Why it matters:
- this is useful later for the receiving and send-to-Amazon parts of the loop

### Use as reference only, not as direct structure

#### Old purchase list mechanics

Reference:
- `reference/Reference only/AMZ Manager 1/ui/purchase_list_classic.py`
- `reference/Reference only/AMZ Manager 1/services/fba_shipment_draft_service.py`

Why not copy directly:
- relies on old `restock_qty` style logic
- uses checkbox-style action columns
- does not reflect the richer decision model now defined in this blueprint

Planning rule:
- keep the useful user-facing familiarity
- do not inherit the old restock data model unchanged

### Reuse summary

For the new operations loop:
- reuse the PO flow ideas
- reuse the supplier commercial-rule ideas
- reuse the backorder and receiving concepts
- reuse the Amazon inbound state/order thinking very heavily
- do not rebuild the old purchase list logic as the new core model

## 16. Recommended Next Execution Ticket

When moving from blueprint to implementation, the first execution ticket should be:

- create `scripts/flows/O/`
- define the exact source contract for the restock source view
- decide the precise forward-ROI formula and thresholds
- implement Phase 1 only: source view, recommendation build, review queue

That gives the cleanest first cut without prematurely forcing PO and receiving into the same ticket.

## 16.1 What should be treated as tuneable after launch

These should be treated as starter operating settings and expected to change with evidence:
- ROI thresholds
- test-restock cover days
- maximum test spend
- stale-demand timing
- lead-time calculation method
- confidence downgrade rules for out-of-stock products
- bulk-long-lead trigger thresholds
- supplier shipping / threshold heuristics

Planning rule:
- where the choice is between endless theory and evidence-led tuning, prefer a clear v1 default plus review logging

## 17. Bottom-Line Recommendation

Use the old Google Sheets system as a behavior reference only, not as a structure reference.

The strongest design is:
- `O` as the new flow family
- `sku_performance_summary.csv` as the merged analytics source to strengthen further
- `inventory_summaries.csv` as stock truth
- `product_db_preview.csv` as the interim supplier-side cost source
- new O-owned live tables only for brand-new workflow state

Most important business rule for the implementation:
- a SKU can only be recommended for restock if it still works at the current buy cost and current market sale price, not because it used to work at an old cost.
