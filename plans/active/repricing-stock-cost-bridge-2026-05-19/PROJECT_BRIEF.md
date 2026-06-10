# Project Brief

## Goal
Build a safe plan for connecting supplier price-list cost, actual purchase cost, and stock/reorder decisions.

Plain-English target:
- Price lists tell us what the supplier says the product costs today.
- Purchase records tell us what we actually paid.
- The stock decider should use the best expected next purchase cost, not blindly trust either source.
- If the expected next cost depends on an assumed discount, the user must be asked to confirm before the system treats it as trusted.

## Why This Matters
The restock engine already has a place for `current_supplier_buy_cost_gbp`, but it currently cannot explain whether that number came from:
- a current supplier price list
- an old purchase
- a discount that may happen again
- a user-confirmed price
- an uncertain or bad source

That is like building a shopping list with prices written in pencil and ink mixed together. The plan must separate them before the system recommends buying stock.

## Current Decision Rule To Model
User rule to implement after approval:
- If price list cost is GBP 2.00 and actual paid cost is GBP 2.00, treat the price-list cost as trusted for the next update.
- If price list cost is GBP 2.00 and actual paid cost is GBP 1.80, remember a 10 percent discount.
- If the next price list moves to GBP 2.50, estimate expected next cost as GBP 2.25, but mark it for user confirmation.
- The stock decider needs a max purchase price so it knows when the product stops making enough money.

## Safety Boundary
This plan is research and planning only.

No implementation is approved yet.

No Google Sheets change is approved.

No local DB alignment change is approved.

No live F, H, A, B, E, or O run is started by this plan.
