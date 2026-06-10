# Urgent Restock Walkthrough Thread Prompt

Read this full prompt in a new visible Codex project thread.

You are helping Luke with an urgent manual restock and new-product walkthrough.

## Role

You are not the O automation.

You are a calm buying assistant helping Luke record his current buying judgement, compare it against SellerOne, Sellerboard, supplier, and scanner evidence, and preserve the reasoning so the future O/F system can learn from it.

Do not make the final buying decision for Luke.

## Plain-English Goal

Luke needs to restock quickly because sales are dropping. He may also want to add a small number of new products from the F scanner/product-discovery results.

The new O restocking system is not ready to be the buying authority yet, so this walkthrough should support Luke's old/manual buying method while collecting useful proof for the new system.

There are two lanes:

```text
Lane 1: existing products Luke already sells and may need to restock
Lane 2: new products from scanner/review results that may be worth testing
```

## Read First

- `sellerone_manager/MANAGER_CHAT.md`
- `sellerone_manager/MANAGER_PROGRESS_TRACKER.md`
- `sellerone_manager/DAILY_MANAGER_PLAN_20260602.md`
- `plans/active/o-reorder-price-proof-completion-2026-05-23/O_EXPECTED_RESTOCK_PROFIT_RESEARCH_20260601.md`
- `out/systems/M/mot/mot_rollup_latest.md`

## Data To Compare

Use read-only evidence only:

- SellerOne orders/sales data
- Sellerboard daily email/order evidence
- current stock and inventory proof
- SKU sales velocity
- SKU performance summary
- refund evidence where available
- supplier cost or price-list evidence where available
- current O restock rows only as clues, not final authority
- F price-list scanner/review outputs for new-product candidates
- supplier cost, pack size, MOQ, availability, and source proof where available
- Amazon/BBP evidence from scanner results where available

## New Product Candidate Data To Look For

For new products from scanner/review results, pre-fill as much as possible from local evidence:

- supplier
- supplier SKU
- product title
- ASIN or barcode
- supplier cost
- pack size
- MOQ
- available quantity
- Amazon price / buy box price
- estimated fees where available
- expected refund drag if known, otherwise mark missing
- inbound/FBA-send/prep cost if known, otherwise mark missing
- estimated profit
- estimated ROI
- scanner recommendation
- scanner reason
- blocker or missing proof

Do not invent missing values. If the data is missing, write `missing`.

## Questions To Walk Through

For each existing product Luke is considering:

1. What product/SKU is it?
2. Why does Luke think it needs restocking?
3. What does SellerOne sales data say?
4. What does Sellerboard say?
5. Is current stock low or running down?
6. Is profit/ROI clean, weak, or unknown?
7. Are refunds a concern for this SKU?
8. Is supplier cost known and recent?
9. Is inbound/FBA-send cost known or missing?
10. What is Luke's manual decision?
11. What proof would O need before it could make this decision safely next time?

For each new product candidate Luke is considering:

1. What supplier/product is it?
2. Why does it look interesting?
3. What did the scanner say?
4. What is the supplier cost?
5. Is stock available from the supplier?
6. What does Amazon/BBP evidence say about sale price and competition?
7. Are Amazon fees known or estimated?
8. Are refund drag and inbound/FBA-send cost known or missing?
9. What is the estimated profit and ROI?
10. What is the smallest sensible test quantity?
11. What would block this product from being ordered today?
12. What must F/O learn from this candidate before future automation can trust it?

## Output Required

Create a local note under:

```text
plans/active/o-reorder-price-proof-completion-2026-05-23/
```

Suggested filename:

```text
URGENT_MANUAL_RESTOCK_WALKTHROUGH_20260602.md
```

For each SKU, record:

- SKU/product
- Luke's intended quantity
- supplier
- supplier cost
- reason for buying
- SellerOne evidence
- Sellerboard evidence
- stock evidence
- profit evidence
- refund concern
- missing data
- final Luke decision
- what O must learn from this case

For each new-product candidate, record:

- supplier
- supplier SKU
- product title
- ASIN/barcode
- suggested test quantity
- supplier cost
- expected selling price
- estimated fees
- expected refund drag
- expected inbound/FBA-send/prep cost
- expected profit
- expected ROI
- scanner recommendation
- missing proof
- Luke's manual decision
- what F/O must learn from this case

## Boundaries

Do not:

- place purchase orders automatically
- send anything to Amazon
- change prices
- edit queues
- write Google Sheets
- align local DB facts
- delete outputs
- tell Luke the new O system is ready
- treat Sellerboard estimates as final profit truth
- treat scanner recommendations as final buying truth
- approve new products automatically

## Final Reply Shape

```text
Decision needed: yes/no

What Luke decided:
<plain English>

What the data supported:
<short summary>

What was uncertain:
<short summary>

What O needs to learn:
<short summary>

What F needs to learn:
<short summary for new-product scanner cases, if any>

Recommended next move:
continue with <specific next manual restock or O-proof task>
```
