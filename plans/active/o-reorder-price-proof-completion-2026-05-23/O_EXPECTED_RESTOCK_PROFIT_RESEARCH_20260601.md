# O Expected Restock Profit Research - 2026-06-01

## Plain-English Finding

O cannot safely call expected restock profit complete until it carries the real cost drags that happen after a sale.

Today O has useful price-proof and net-fee scaffolding, but refund drag and inbound/FBA-send cost are not yet reliable enough to treat a restock profit number as final.

This does not mean O is broken. It means O should keep rows in review/check-price mode until the missing profit inputs are labelled and modelled.

## Evidence Read

- `out/order_master.csv`
  - 11,360 rows
  - 161 distinct SKUs
  - current through 2026-06-01
- `out/sku_performance_summary.csv`
  - 161 rows
  - current as of 2026-06-01
  - has `expected_refund_cost_per_unit_gbp`, but it is zero for every row
- `out/systems/O/live/restock_source_view.csv`
  - 608 rows
  - has `expected_refund_cost_per_unit_gbp`, but it is zero for every row
  - missing refund confidence fields such as refund rate, refund units, sales units, proof state, and sample confidence
- `out/systems/O/live/restock_profit_checks_live.csv`
  - 608 rows
  - has `refund_drag_gbp`, but it is zero for every row
  - has fee drag for 161 rows
- `out/financial_events_refunds_official.csv`
  - 212 refund rows
- `out/refund_token_events.csv`
  - 212 refund token rows
  - 25 SKUs had refund activity in the last 90 days
- `out/transaction_expense_allocations.csv`
  - 146 rows
  - all 146 rows are unallocated
  - absolute unallocated amount inspected: 1,214.51 in source currencies
- `out/inbound_cost_events.csv`
  - 32 inbound cost event rows
  - absolute amount inspected: 186.79
- `out/inbound_costs_allocated_sku.csv`
  - 0 rows
- `out/fee_detail_ledger_api.csv`
  - 0 rows
- `out/systems/O/live/reorder_input_coverage_report.csv`
  - 608 rows
  - 0 action-ready rows
  - 160 rows have fresh net-fee proof
  - 448 rows have missing net-fee proof

## Refund Evidence Examples

These are not final business decisions. They show why refund drag must not stay silently zero.

| SKU | 90d sold units | 90d refund units | 90d refund rate | refund drag per sold unit |
|---|---:|---:|---:|---:|
| LR-7GM6-1RCH | 11 | 3 | 27.27% | 8.36 |
| 8W-I703-VOFQ | 2 | 1 | 50.00% | 7.34 |
| MW-9K5M-VKW8 | 20 | 5 | 25.00% | 4.84 |
| LV-425G-BY4X | 59 | 2 | 3.39% | 1.48 |
| GJ-2OZK-0GCA | 29 | 1 | 3.45% | 0.81 |

## Profit Formula O Should Use

Expected restock profit per sellable unit should be:

```text
expected sell price ex VAT
- supplier buy cost ex VAT per sellable unit
- Amazon fee drag ex VAT
- expected refund drag per sold unit
- expected inbound/FBA-send/prep cost per sellable unit
= expected forward profit per unit
```

Then Max Pay should be:

```text
maximum safe buy cost
= expected sell price ex VAT
- Amazon fee drag
- expected refund drag
- expected inbound/FBA-send/prep cost
- required target profit
```

## Information O Ideally Needs Before Restocking

1. Current sell price proof
   - current Amazon market price
   - price basis: buy box, our live price, legacy Sheet backsolve, or manual check
   - timestamp and freshness

2. Current buy cost proof
   - supplier list cost
   - usual paid cost
   - last paid cost
   - confirmed typed cost before buying
   - pack/case conversion to one sellable unit

3. Amazon fee drag
   - referral/commission
   - FBA fulfilment fee
   - digital or fixed closing fee where relevant
   - VAT treatment
   - fee proof source and freshness

4. Refund drag
   - refund units by SKU for 30/90/180 days
   - sold units by SKU for the same windows
   - refund rate
   - net refund cost per sold unit
   - proof confidence: strong SKU sample, weak SKU sample, parent/category fallback, or unknown
   - source timestamp

5. Inbound/FBA-send/prep cost
   - inbound transport charge
   - shipment id
   - received units by SKU in that shipment
   - allocated inbound cost per sellable unit
   - fallback supplier/category average where SKU allocation is not available
   - proof confidence and timestamp

6. Demand and stock cover
   - 7/30/90 day velocity
   - available stock
   - inbound stock
   - days of stock left
   - out-of-stock days so demand is not understated

7. Business guardrails
   - target ROI or target profit
   - minimum review sample size
   - do-not-buy flags
   - hazmat, bulky, long lead, MOQ, and pack constraints

## Required O Field Updates

Add or populate these fields into O source/profit proof:

- `refund_units_30d`
- `refund_units_90d`
- `sales_units_30d`
- `sales_units_90d`
- `refund_unit_rate_30d`
- `refund_unit_rate_90d`
- `refund_drag_per_sold_unit_gbp`
- `refund_cost_basis`
- `refund_proof_state`
- `refund_sample_confidence`
- `refund_source_asof`
- `expected_inbound_cost_per_unit_gbp`
- `inbound_cost_basis`
- `inbound_cost_confidence`
- `inbound_cost_source_asof`
- `expected_total_non_buy_cost_drag_gbp`
- `profit_input_confidence`

## Safe Build Conclusion

The next safe O build should not create purchase orders or receiving flow.

The next safe O build should create a read-only expected-profit input model that:

- treats missing refund/inbound data as unknown, not zero
- shows the proof state beside each product
- blocks clean buy readiness when refund, inbound, fee, market price, or buy cost proof is missing or weak
- keeps the current user-working state intact

## Forbidden During This Research Path

- No Google Sheets writes
- No price changes
- No queue edits
- No local DB alignment
- No purchase orders
- No receiving events
- No send-to-Amazon handoff
- No output deletion
- No H pause/resume
- No market proof scan
