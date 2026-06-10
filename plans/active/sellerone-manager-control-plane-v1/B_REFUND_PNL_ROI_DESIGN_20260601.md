# B Refund To P&L To ROI Design - 2026-06-01

## Plain-English Summary

Refunds should work like a returned item in a shop till.

The system needs to know:

- which original order was refunded
- which SKU was refunded
- how many units were refunded
- how much customer money was returned
- what VAT moved
- what Amazon fees were reversed
- whether stock/COGS came back into usable inventory
- how that changes profit
- how often that SKU gets refunded
- whether ROI/restocking should trust the refund-adjusted profit

Sellerboard is useful as the outside witness that says an order became a return. Amazon/API remains the money source because it gives the order id, SKU, refund amounts, VAT, fee reversals, and refund date.

## Current State

The system already has useful refund pieces:

- `out/financial_events_refunds_official.csv` gives API refund rows by order id and SKU.
- `out/financial_events_refunds.csv` gives raw refund money components.
- `out/refund_token_events.csv` records refund events against stock/token records.
- `out/token_ledger_live.csv` stores returned token markers.
- `out/pnl_daily.csv` already has refund P&L lines such as `Refund_Sales_Total`, `Refund_Expenses_Total`, and `Refund_Commission`.
- `out/sku_performance_summary.csv` already has `expected_refund_cost_per_unit_gbp`, but this is not yet fully proven as a clean unit refund-rate model.
- Sellerboard bridge can confirm return status from the daily email.

The gap is not "no refund data".

The gap is proving the whole money chain:

```text
API refund row
-> original order and SKU
-> refund unit count
-> refund money impact
-> daily P&L
-> SKU refund percentage
-> ROI refund drag
-> E/O restock confidence
```

## Target Outputs

### 1. Refund Order Bridge

Create a local proof file:

```text
out/systems/B/refunds/b_refund_pnl_bridge.csv
```

One row per refunded order/SKU.

Required columns:

- `order_id`
- `sku`
- `marketplace`
- `original_purchase_date`
- `refund_posted_date`
- `original_order_status`
- `original_units`
- `refund_units`
- `original_price_total`
- `original_price_exvat`
- `refund_price_total`
- `refund_price_vat`
- `refund_price_exvat`
- `refund_shipping_total`
- `refund_commission_total`
- `refund_digital_fee_total`
- `refund_fba_fee_total`
- `refund_other_fee_total`
- `return_cogs_recovered_exvat`
- `refund_profit_impact_exvat`
- `sellerboard_status`
- `sellerboard_match_state`
- `api_refund_proof_state`
- `pnl_inclusion_state`
- `notes`

Purpose:

- This becomes the audit bridge between Amazon refund data and our business profit view.
- This file must not edit orders, tokens, P&L, E, or O by itself.
- It is proof first, then downstream scripts consume it.

### 2. SKU Refund Rate

Create a local proof file:

```text
out/systems/B/refunds/b_sku_refund_rate.csv
```

One row per SKU and window.

Required columns:

- `sku`
- `window_days`
- `sales_units`
- `refund_units`
- `net_units`
- `refund_unit_rate`
- `refund_order_count`
- `sales_order_count`
- `refund_sales_total_gbp`
- `refund_fee_reversal_total_gbp`
- `refund_profit_impact_gbp`
- `expected_refund_cost_per_unit_gbp`
- `basis`
- `sample_confidence`
- `proof_state`

Use two basis types:

- `posted_window`: refunds posted in the window divided by units sold in the same window.
- `sale_cohort`: refunds attached to orders sold in the window divided by units sold in that window.

Plain-English rule:

- `posted_window` is useful for recent business drag.
- `sale_cohort` is cleaner, but it can lag because refunds happen after the sale.
- ROI should prefer the most stable proven basis, not whichever number looks nicer.

### 3. P&L Integration

Daily P&L should include refund money as it already does, but it also needs unit proof.

Add or prove these P&L rows:

- `Refund_Units`
- `Gross_Units_Sold`
- `Net_Units_Sold`
- `Refund_Unit_Rate`
- `Refunded_Order_Count`

Important protection:

- First audit whether refunds are being counted once or twice in `D001_build_pnl_daily.py`.
- The current script reads official refund rows and also has transaction-ledger refund handling. The worker must prove this is not double-counting before adding more refund rows.

### 4. ROI Integration

E should not calculate ROI with a vague refund allowance.

E should consume the SKU refund-rate proof and carry these fields:

- `refund_unit_rate_30d`
- `refund_unit_rate_90d`
- `refund_units_30d`
- `sales_units_30d`
- `expected_refund_cost_per_unit_gbp`
- `refund_cost_basis`
- `refund_proof_state`
- `refund_sample_confidence`

ROI should use:

```text
expected refund drag per sold unit
= refund profit impact over the chosen window / sales units over the chosen window
```

Then:

```text
refund-adjusted ROI
= profit after normal cost and fees and expected refund drag / cost
```

Plain-English rule:

- If refund proof is clean, E can mark profit as cleaner.
- If refund proof is weak or sample size is too small, E can still calculate the number, but it must label it as lower confidence.
- O must not treat weak refund proof as a fully safe restock decision.

### 5. Sellerboard Role

Sellerboard daily email should be used as outside witness only.

Use it to answer:

- Did Sellerboard see this order as returned?
- Did Sellerboard see a return that Amazon/API has not posted yet?
- Did Amazon/API show a refund that Sellerboard did not call a return?

Do not use Sellerboard values as final refund money unless Luke separately approves a bridge rule.

## Manager MOT Checks

Add or extend B/E MOT checks:

- API refund rows exist and are fresh.
- Every API refund row with order id and SKU appears in `b_refund_pnl_bridge.csv`.
- Refund bridge money totals reconcile to official refund money totals.
- P&L refund money rows reconcile to the bridge.
- Refund units reconcile to bridge rows.
- `b_sku_refund_rate.csv` exists and covers active sold SKUs.
- E performance summary carries refund-rate and refund-proof fields.
- O source view carries refund drag and proof state.
- Sellerboard return-only gaps stay warning-labelled, not hidden.

## Acceptance Criteria

The task is ready when:

- One recent refund can be traced from API refund row to P&L and E ROI fields.
- SKU refund percentage is visible for 30-day and 90-day windows.
- P&L shows refund units as well as refund money.
- E ROI has refund proof labels.
- O restock rows can tell clean refund proof from weak proof.
- MOT shows refund/P&L/ROI proof as ok or honest warning.
- No Sheets, prices, queues, output deletion, or local DB alignment are used to prove it.

## Protected Boundaries

Do not:

- write Google Sheets
- change prices
- edit queues
- publish
- align local DB facts to make numbers match
- delete outputs
- run live B/E/O cycles without an approved proof window
- use Sellerboard estimates as final ROI/restocking truth
- make business restock decisions

## Suggested Implementation Order

1. Build `b_refund_pnl_bridge.csv` from existing API refund rows and order data.
2. Build `b_sku_refund_rate.csv`.
3. Prove whether current P&L refund rows double-count or count once.
4. Add refund unit rows to P&L.
5. Feed refund-rate proof into E performance summary.
6. Feed refund-proof labels into O source view.
7. Add MOT checks and tests.
8. Run read-only proof and focused tests.

## Thread Prompt

Use this project thread prompt:

```text
sellerone_manager/project_threads/08_B_REFUND_PNL_ROI_THREAD.md
```

