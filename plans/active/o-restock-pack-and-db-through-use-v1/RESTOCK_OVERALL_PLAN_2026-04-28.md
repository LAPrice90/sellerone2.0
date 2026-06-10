# Restock Overall Plan - 2026-04-28

Created UTC: 2026-04-28T09:41:47Z

## 1. Current Interpretation

The open restock work is in:

- `plans/active/o-restock-pack-and-db-through-use-v1`

The repo already has an isolated `O` flow. It is not live-loop ready, but it has the right skeleton:

- restock source view
- restock recommendations
- restock review queue
- decision events
- purchase order outputs
- ordered-stock state
- receiving events
- send-to-Amazon queue
- operator UI

The current plan status says:

- current stage: implementation in progress
- current phase: Phase 2 - Sample-only test orders page
- current batch: Batch 002 in progress
- real SKU onboarding: still blocked until later approval

My interpretation:

- We are past pure theory.
- The sample-product ordering UI exists far enough to use for learning.
- The next useful work is not a new plan from scratch.
- The next useful work is to finish the sample path, harden blocker reporting, then run a small sample walkthrough from recommendation to order list.

## 2. Current Data Reality

Latest O artifact evidence found:

| Artifact | Current state |
| --- | --- |
| `out/systems/O/live/restock_source_view.csv` | 608 rows, modified 2026-04-10 |
| `out/systems/O/live/restock_recommendations_live.csv` | 10 sample UI rows, modified 2026-04-04 |
| `out/systems/O/live/restock_review_queue.csv` | 10 sample UI rows, modified 2026-04-04 |
| `out/systems/O/inbox/restock_decision_events.csv` | 22 sample/operator events, modified 2026-04-17 |
| `out/systems/O/live/purchase_orders_live.csv` | header only |
| `out/systems/O/live/purchase_order_lines_live.csv` | header only |
| `out/systems/O/live/ordered_stock_state.csv` | header only |
| `out/systems/O/live/send_to_amazon_queue.csv` | 0 rows |
| `out/systems/O/live/reorder_input_readiness_summary.md` | old readiness snapshot from 2026-04-04 |

Important meaning:

- The source view has real-like upstream rows.
- The recommendation and review queue currently contain preview/sample rows, not true live recommendations.
- Purchase order, ordered stock, receiving, and send-to-Amazon outputs exist as contracts, but they are not populated by a proven live workflow yet.
- The readiness summary is stale context and must not be used as current proof.

## 3. User Workflow We Should Build Toward

The operator should not have to leave SellerOne to decide what to buy.

User-confirmed workflow rule:

- The supplier is the unit of work.
- The operator always starts with a supplier.
- Products from different suppliers must not be mixed into one ordering session.
- Once a supplier is started, the UI should help complete that supplier from start to finish before moving on.
- This matters because supplier ordering often means filling one supplier basket or writing one supplier email.

User-confirmed supplier-worth rule:

- The first supplier question is: is this supplier worth ordering from today?
- Supplier minimum order and delivery rules are part of that answer.
- Example: Stax has a minimum order requirement of about GBP 400. If recommended stock is only about GBP 200, the supplier should usually be skipped for now.
- Example: Jones Wholesale has a delivery minimum order value of GBP 300 ex VAT and free delivery at GBP 600 ex VAT.
- If an order meets a minimum but still has a delivery charge, that delivery charge must be split across the proposed products before deciding whether the order is profitable.
- If the supplier-level order economics do not work, the system should avoid prompting the user for recommended orders from that supplier.
- The system should eventually make this supplier-worth decision automatically, but the rules must be built from the user's real process first.

Required supplier profile data:

- supplier name
- supplier code
- minimum order value
- free delivery threshold
- expected delivery charge below free-delivery threshold
- VAT basis for thresholds, such as ex VAT or inc VAT
- whether shipping should be allocated across order lines for forward ROI
- whether a below-threshold supplier should be hidden, snoozed, or shown as "not worth ordering today"
- whether supplier stock is available from a live website, supplier file, email file, API, or manual check
- supplier stock freshness rule, such as same day, last 24 hours, or latest supplier file

User-confirmed shipping allocation rule:

- Default shipping allocation should be by line value.
- Reason: a GBP 50 product should carry more of a GBP 50 delivery charge than a GBP 1 product.
- Example:
  - if supplier shipping is GBP 50
  - and the proposed order value is GBP 300
  - then a line worth GBP 50 carries about 16.7 percent of shipping, or GBP 8.33
  - a line worth GBP 1 carries about 0.33 percent of shipping, or about GBP 0.17
- This allocated shipping cost should be added to that line's forward buy cost before final ROI/profit decision.
- Do not use equal per-product shipping split as the default.
- Future exception: weight, size, hazmat, or bulky-product suppliers may need a different allocation method later, but do not overbuild this before real feedback.

User-confirmed app notification rule:

- The supplier-worth check should happen before the user opens the supplier.
- The morning script should decide which suppliers are worth attention today.
- The UI should behave like a tablet/app screen:
  - each business function feels like an app
  - restock has a notification badge when suppliers need review
  - the user works through script-raised notifications instead of manually checking every supplier
- The restock app badge number means suppliers ready to review, not product rows.
- Example: badge `3` means 3 suppliers are ready for review.
- If a supplier reaches its minimum order value but shipping makes the order unviable, the system should not prompt it as ready.
- In that case, the supplier should be checked again on the next calculation window, such as tomorrow morning.
- If the supplier reaches a better threshold, such as free delivery or enough margin after shipping, the supplier becomes a notification.
- Supplier stock availability must be part of readiness where a live or recent supplier-stock input exists.
- If products are out of stock at the supplier and the realistic order value drops below the supplier-worth threshold, the supplier should not keep appearing as ready every day.
- Out-of-stock supplier rows should stay visible in diagnostics or a waiting state, but should not create repeated ready-to-review prompts unless enough available value remains.

User-confirmed supplier cadence rule:

- Supplier order timing should be supplier-aware, not one fixed monthly rule.
- Some slower or less attractive suppliers may only be worth ordering every 60 or 90 days.
- A supplier can be commercially viable but still not worth small frequent orders.
- The system should learn or classify whether a supplier is best handled as:
  - frequent order
  - monthly order
  - 60-day order
  - 90-day / quarterly order
- For slower suppliers, the system may recommend a larger cover target so the order is worth doing when the supplier is opened.
- This supplier cadence should affect whether a supplier gets a notification today.

User-confirmed supplier stock and friction rule:

- Supplier stock input varies by supplier.
- Ideal future source is supplier API where available.
- Other valid supplier stock sources include:
  - supplier CSV link
  - daily supplier email
  - supplier website lookup
  - basket/add-to-cart check
  - manual user check
  - unknown / no stock visibility
- Each supplier may need its own upstream collection method, but restock should read a normalized supplier-stock result.
- Suppliers with no reliable stock visibility may need a snooze/check-back workflow rather than daily prompting.
- Supplier ease-of-use should become part of supplier scoring.
- A low-profit supplier is not automatically bad if it takes very little user time.
- A low-profit supplier that takes too much user time should be downgraded or eventually removed from active restock prompting.
- Example thinking:
  - a supplier making about GBP 50 per month might still be worth keeping if it only needs about 20 minutes once per quarter
  - the same profit may not be worth it if it creates frequent manual work or uncertainty

Future supplier score inputs:

- monthly or quarterly profit contribution
- user time required per order
- order frequency
- stock data availability
- supplier data freshness
- API / CSV / email / website / manual source type
- delivery cost and free-delivery threshold
- backorder reliability
- price-change frequency
- supplier response quality
- number of viable SKUs
- operational friction rating

User-confirmed stock-unknown supplier workflow:

- Suppliers with no usable live stock information are usually the ones that require email or account-manager contact.
- Current human workaround is usually to snooze products week to week.
- V1 should support a stock-check message template and snooze option in the UI.
- The user should be able to review the proposed stock-check list for that supplier and generate supplier-ready text.
- The initial version can keep sending manual, but the system should prepare the message cleanly.
- A later version can send the email automatically from SellerOne.
- A later version can use an AI/API reply parser to interpret supplier replies and update availability, price, backorder, and suggested snooze state.
- Where website stock is the only source, a future browser/scraping worker may open Chrome or run a supplier-specific check.
- The long-term operating model is that the user manages automated workers rather than manually doing every supplier check.

Stock-unknown UI behavior:

- Do not show stock-unknown rows as clean recommended orders.
- Show them as "Needs stock check" or similar human wording.
- Provide:
  - supplier-ready stock-check text
  - copy button
  - optional email-send path later
  - snooze date
  - note field for reply outcome
- If the supplier reply confirms stock and price, the supplier can re-enter the ready-to-review path.

Initial stock-check message template:

- Use a simple product-line format first:
  - `SUPPLIER-CODE - need 12 units - please confirm stock and price`
- The UI can generate one line per product for the supplier.
- This text should be easy to copy into email or supplier chat.
- Treat the wording as tunable from real use.
- Do not over-design message wording before the operator has tried it on real suppliers.

User-confirmed supplier screen summary:

- The supplier order screen should start with a compact supplier-worth summary.
- Most useful top-line fields:
  - total order value
  - expected profit after shipping
  - estimated shipping charge
- Threshold gaps are useful but should not be wordy.
- Use a visual threshold/loading bar for minimum order and free-delivery progress.
- Example:
  - if paid-shipping minimum is GBP 300
  - and free delivery is GBP 600
  - the bar can use GBP 600 as 100 percent
  - show a marker at GBP 300 for paid-shipping eligibility
  - show the current order value as progress toward GBP 600
- If order value exceeds the free-delivery threshold:
  - order value becomes the filled 100 percent state
  - free-delivery threshold becomes a marker/checkpoint rather than the end of the scale
- Avoid long explanatory text in the main supplier header.

User-confirmed supplier inbox model:

- Ready suppliers should behave like highlighted app notifications.
- Once reviewed, they should no longer be highlighted as new, but should still be accessible.
- Suppliers that are not ready should not disappear completely.
- Use tabs or sections so the user can still open quieter supplier states.
- Suggested supplier list order:
  - ready / notified suppliers at the top
  - below that, not-ready suppliers sorted by threshold progress
  - suppliers closest to 100 percent should appear highest in the quieter list
- Each supplier row/card should show the threshold/loading bar so the user can see how close it is to being worth attention.
- The UI should allow manual opening without turning every supplier into a daily prompt.

Initial supplier inbox tabs:

- Use simple trial tabs first:
  - `Ready`
  - `Building`
  - `Needs Stock Check`
  - `Snoozed`
  - `All`
- Meanings:
  - `Ready` = supplier is worth reviewing now and counts toward the restock app badge.
  - `Building` = supplier is not ready yet but is accumulating order value toward a threshold.
  - `Needs Stock Check` = supplier/product needs manual, email, website, or worker stock confirmation before it can be trusted.
  - `Snoozed` = user or system has delayed the supplier/product until a future date.
  - `All` = manual access to every supplier state.
- Treat the names and splits as trial UI wording.
- If real use shows too many tabs, merge them later.

User-confirmed ready supplier open behavior:

- Clicking a `Ready` supplier should jump directly into the ordering workspace.
- Do not force a separate summary screen before ordering.
- The supplier header summary should still be visible at the top of the ordering workspace.
- The user must always be able to correct supplier stock and supplier price.
- User correction is needed because:
  - API stock can be wrong
  - supplier files can be dated
  - supplier pricing can be slightly wrong
  - the user may have negotiated or found better pricing
- Manual corrected price and stock should apply to the current order decision.
- A manual correction should not automatically rewrite Product_DB or supplier master data without explicit approval.
- Rows should support user actions such as:
  - mark out of stock
  - edit confirmed price
  - edit order quantity
  - snooze
  - note supplier issue

User-confirmed out-of-stock default:

- Marking a product out of stock should remove it from today's order.
- Default result should be a 7-day snooze.
- The UI may allow the user to change the snooze date, but the standard action should be fast.
- The row should not keep returning as ready every morning during the snooze window.

Bulk and normal buy option plan:

- A bulk buy should not be stored as a second product.
- A bulk buy should be stored as a second purchase option for the same SKU.
- The SKU stays singular so the system cannot double-order the normal and bulk version by mistake.
- Example product:
  - supplier: Stax
  - product: HG Stain Away 7
  - supplier code: `426005106`
  - ASIN: `B007R2ICTK`
  - SKU: `WX-L5UA-UB1Q`
- This product can have:
  - normal option from current price list
  - bulk option based on larger quantity / better pricing
- The recommendation engine should compare the options and pick one active proposal.
- It should never recommend both options as separate live orders for the same SKU in the same supplier basket.

Bulk option reasoning:

- Some products have demand higher than supplier stock availability.
- Some products are worth buying several months of stock at once.
- Some products are only attractive at a bulk or negotiated price.
- User-confirmed main bulk reason:
  - it is often better to order 2-3 months of stock at a better bulk unit price than to keep ordering month to month at the normal price.
- For these, the question is not only "do we need stock now?"
- The question is:
  - normal order at normal price?
  - larger order at bulk price?
  - wait / stock check / bulk quote needed?

Bulk price persistence rule:

- A manually entered better price should default to current order only.
- Reason: a better price may be a one-off deal and should not distort future recommendations.
- The UI can later offer a quiet explicit option such as:
  - `Use for this order only`
  - `Save as reusable bulk price`
  - `Save as supplier price update`
- Do not automatically update future supplier cost truth from a manual order correction.
- If saved as reusable, the system must store:
  - minimum quantity for that price
  - whether it is a one-off quote or recurring tier
  - source, such as manual quote, price file, supplier email, or API
  - captured date
  - expiry/review date if known

Suggested purchase option fields:

- `seller_sku`
- `supplier_code`
- `supplier_sku`
- `purchase_option_id`
- `option_label`, such as `Normal` or `Bulk`
- `option_type`, such as `normal`, `bulk`, `quote`, or `price_break`
- `min_order_qty`
- `max_order_qty` if relevant
- `target_cover_days`
- `unit_cost_gbp`
- `cost_source_type`
- `cost_source_reference`
- `captured_at_utc`
- `expires_at_utc`
- `is_one_off_quote`
- `is_reusable`
- `confidence`
- `notes`

Bulk recommendation behavior:

- For normal products, recommend the normal option.
- For bulk-eligible products, calculate normal and bulk options side by side.
- Bulk should usually mean a larger cover target, often around 60-90 days, not just a small normal reorder using a cheaper price.
- Bulk must be data-driven, not "cheap unit price" driven.
- The system should ask: if we buy this bulk quantity, what is likely to happen?
- Compare:
  - stockout risk
  - target cover days
  - capital tied up
  - supplier stock availability
  - forward ROI after shipping
  - total expected profit
  - whether the supplier basket threshold improves because of the larger line
- Add bulk guardrails before recommending the bulk option:
  - expected months of cover
  - expected units sold over the cover window
  - remaining stock after 30 / 60 / 90 days
  - cash tied up
  - expected profit over the cover window
  - break-even time
  - demand confidence
  - market-price stability
  - Amazon/manufacturer risk where known
  - stale-demand or long-stockout risk
  - storage/expiry/oversize risk where known
- Example logic:
  - if the bulk option means buying 800 units
  - but the product sells about 20 units per month
  - then the system should flag that as excessive cover and recommend a smaller order or block the bulk option
- Better price alone is not enough.
- The bulk option should only win when the expected demand, margin, risk, and capital exposure all make sense.

User-confirmed bulk viable UI state:

- Bulk should usually appear on the normal product row, not as a separate product.
- Add a `Bulk viable` state when the product is in a position where a bulk order should be considered.
- Use a maximum bulk cover cutoff so the system does not recommend excessive stock.
- Initial proposed cutoff:
  - maximum bulk cover: 4 months
- If a bulk quantity would create more than the max cover cutoff, the system should reduce, warn, or block the bulk option.
- Once the product is ready for a sensible bulk order, the UI can show a small glowing or highlighted symbol.
- The symbol should mean "bulk option worth reviewing now".
- The main row should still behave as one product row with one selected order choice.
- The symbol should open a compact bulk comparison:
  - normal option
  - bulk option
  - cover months
  - unit cost
  - expected profit
  - cash tied up
  - risk notes
- If bulk looks better but the price is unconfirmed, show `Needs bulk price check`.
- If bulk price is confirmed and economics are better, recommend the bulk option.
- If bulk creates too much stock exposure, recommend normal or wait.

UI behavior for bulk products:

- Show one row for the SKU.
- Use a compact option selector or side-by-side chips:
  - `Normal`
  - `Bulk`
- Default to the system's recommended option.
- Let the user switch option if needed.
- Show the reason briefly, with more detail behind a hover/popover.
- Keep the main row simple:
  - selected option
  - order quantity
  - confirmed unit price
  - expected cover
  - profit/ROI after shipping
- Do not show backend terms like `bulk_review` in the main UI.

Double-order prevention rule:

- A SKU can have multiple purchase options, but only one active order choice per supplier basket.
- If the user switches from normal to bulk, the normal proposal is replaced, not added.
- Purchase order output should contain the selected option ID for audit.
- Decision logs should preserve the options compared so future review can learn whether bulk was the right choice.

The intended daily workflow should be:

1. Morning scripts calculate supplier readiness.
2. Restock app shows a notification badge only when supplier review is worth attention.
3. Open the restock app.
4. Choose one notified supplier section.
5. Review why the supplier is ready today, including order value, minimum order value, free-delivery threshold, shipping cost, and supplier cadence.
6. Review each product row with image, SKU, ASIN, supplier code, barcode, current price, stock, velocity, days cover, ROI, and recommendation.
7. Confirm the current supplier price and final order quantity.
8. Choose the action:
   - Restock
   - Test
   - Wait
   - Snooze
   - Drop for now
9. Send approved rows into a test order list or PO draft.
10. Confirm supplier response:
   - accepted quantity
   - changed price
   - backorder
   - unavailable
   - canceled remainder
11. Receive stock against the PO.
12. Move received stock into a send-to-Amazon queue.
13. Create Amazon inbound shipment only after box contents are locally known and validated.

Plain-English target:

- The human decides.
- SellerOne carries the data, maths, history, and handoff state.
- No manual copy/paste between separate systems should be needed except supplier communication where a supplier still needs email or website ordering.

## 4. Storage And Conflict Rules

The safest structure is event-first and state-second.

Use append-only logs for actions:

- restock decision events
- supplier confirmation events
- receiving events
- send-to-Amazon handoff events
- shipment packing events later

Use rebuilt state tables for current views:

- review queue
- purchase orders live
- purchase order lines live
- ordered stock state
- send-to-Amazon queue

This avoids conflicts because:

- user actions are never silently overwritten
- current state can be rebuilt from events
- O owns only workflow state
- A/B/E/H remain the source of stock, sales, performance, and market truth
- Product_DB preview remains read-only until explicit approval changes that boundary

Do not create a second copy of A/B/E/H truth just to make O easier.

## 5. Stale Data Protection

Every restock decision row must carry source timestamps or source references.

Minimum stale-data rules for v1:

- A stock snapshot must be visible on the row.
- E velocity/performance source date must be visible or at least carried in the row.
- H market price source timestamp must be visible or carried in the row.
- Product/supplier cost source must be labelled.
- Preview/sample rows must not be promotable into live purchase orders.
- A row cannot be action-ready if the source data is missing or too old for the selected mode.
- A confirmed user price can override the suggested price for that order, but only as order truth, not as a Product_DB rewrite.

For sample mode:

- allow old/sample data
- label it clearly as sample/test
- block live PO creation

For live mode:

- block if source freshness is unknown
- block if the row is still `ui_preview_sample`
- block if quantity conversion is unsafe

## 6. Pack And Quantity Rules

The active plan already locked the correct direction:

- simple unit SKUs can use raw units
- supplier case SKUs must respect case multiples
- repack SKUs let the operator think in Amazon sell packs while the system converts to raw supplier units
- bundle SKUs must make bundle maths explicit

The key rule:

- the operator should type the quantity in the unit that makes sense to them
- the system should convert it to raw units and supplier cases
- invalid quantities should be blocked or corrected before order submission

Next required blocker reasons:

- missing quantity mode
- missing sell pack quantity
- missing supplier case quantity
- invalid pack conversion
- invalid supplier case multiple
- missing supplier SKU or supplier code

## 7. Old AMZ Manager 1 Reuse

The old AMZ Manager system should be used as a reference, not copied as the new data model.

Useful references found:

- `reference/Reference only/AMZ Manager 1/ui/po_builder.py`
- `reference/Reference only/AMZ Manager 1/services/po_flow_service.py`
- `reference/Reference only/AMZ Manager 1/services/fba_inbound_service.py`
- `reference/Reference only/AMZ Manager 1/services/spapi_inbound_client.py`
- `reference/Reference only/AMZ Manager 1/docs/fba_shipment_workflow.md`
- `reference/Reference only/AMZ Manager 1/docs/fba_integration.md`
- `reference/Reference only/AMZ Manager 1/docs/fba_inbound_state.md`

What to reuse:

- staged PO flow
- supplier confirmation stage
- backorder/cancel handling
- receiving against confirmed lines
- expected-date and overdue thinking
- local Amazon inbound plan state
- local packing state
- idempotent reruns
- blocking transport/labels until packing is submitted

What not to reuse:

- old restock data accuracy assumptions
- old purchase-list formula logic
- checkbox/delete style as the core model
- any structure that hides source truth or mixes recommendation, order, receiving, and shipment state in one table

## 8. Send-To-Amazon API Planning Rule

This is the rule to avoid the old "boxes with no contents" problem:

- SellerOne must store box contents before sending packing/transport steps to Amazon.
- Box item totals must exactly reconcile to shipment item totals.
- The UI must block progression if any box has no contents.
- The UI must block progression if total box SKU quantities do not match the shipment SKU quantities.
- Transport/label steps must only unlock after packing has been submitted and stored.

Suggested state sequence:

1. send-to-Amazon draft
2. Amazon plan created
3. placement confirmed
4. boxes entered locally
5. box contents validated
6. packing submitted to Amazon
7. transport option selected
8. labels generated/stored
9. shipment marked dispatched
10. Amazon status synced back

## 9. This Week Execution Plan

### Tuesday 2026-04-28 - close the sample ordering lane

Goal:

- prove the sample flow from recommendation queue to Test Orders page.

Work:

- rerun targeted O UI tests
- confirm Test Orders page reflects submitted sample decisions
- update plan status if the existing Phase 2 proof is still true
- keep all rows in sample/test mode

Output:

- Phase 2 either closed or named with exact blocker

### Wednesday 2026-04-29 - pack-aware blocker reporting

Goal:

- stop unsafe rows before they reach order submission.

Work:

- implement pack and quantity blocker reasons in O coverage and diagnostics
- add tests for missing and invalid pack truth
- make blocker summary readable without code knowledge

Output:

- sample rows can say exactly why they are order-ready or blocked

### Thursday 2026-04-30 - order list / PO draft sample lane

Goal:

- turn approved sample decisions into a supplier-grouped order list.

Work:

- build or harden the sample PO draft view from decision events
- group by supplier
- show supplier order text such as `SupplyCode x Qty`
- keep it separate from live PO outputs unless explicitly approved
- include supplier response fields:
  - confirmed quantity
  - confirmed price
  - backorder
  - unavailable
  - canceled

Output:

- sample products pass from reorder board into a clean order list / PO draft

### Friday 2026-05-01 - receiving and send-to-Amazon sample design

Goal:

- define the next handoff stages before live data enters.

Work:

- run sample rows through ordered-stock state
- define receiving event behavior
- define send-to-Amazon queue behavior
- create the inbound shipment checklist based on AMZ Manager 1 reference
- do not call Amazon API yet

Output:

- sample flow is proven as a local walkthrough from restock decision to send-to-Amazon-ready queue

## 10. Switch To Live Info Gate

Do not switch to live info until all are true:

- sample Test Orders path is closed and proven
- pack blocker reporting exists
- sample PO draft/order list is proven
- sample ordered-stock state is proven
- live rows can prove source freshness
- preview/sample recommendation rows cannot accidentally create live POs
- user explicitly approves the real SKU sample

First live sample should be tiny:

- 3 to 5 approved SKUs
- read-only from Product_DB preview
- no Google Sheet writes
- no Product_DB authority change
- no Amazon inbound API calls
- no live PO commitment until explicitly approved

## 11. Best Next Ticket

Best immediate ticket:

- finish `O Restock Phase 2 / Batch 002` by proving or fixing the sample Test Orders page

Then:

- run Phase 3 pack-aware blocker reporting

Then:

- build the sample order list / PO draft lane

This is the cleanest path to getting sample products through the system this week without interrupting MOT, B, F, or H.
