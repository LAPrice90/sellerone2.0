# Token Process: Stock-First, Demand-Bounded (2025-11-01 anchor)

## Goal
Create tokens only for the required slice of reality:
`target_tokens = net_orders_since_cutoff + current_stock`.
Purchases define **cost allocation** only, not token counts.

## Inputs
- Orders: `out/order_master.csv` (net of refunds since 2025-11-01)
- Inventory: `out/inventory_summaries.csv`
- Purchases: `out/orders_sheet_orders.csv` (used for costs only)

## Rules (authoritative)
1) Orders since 2025-11-01 drive demand.
2) Stock tokens are created **first**.
3) Purchase rows are consumed **bottom-up** (newest row first).
4) Sent-to-FBA caps stock tokens per purchase row.
5) Ordered caps order tokens per purchase row.
6) Anything beyond `target_tokens` is ignored.

## What the build does
1) Compute net demand per SKU from orders minus refunds.
2) Read current stock per SKU.
3) For each SKU:
   - target = demand + stock
   - create tokens from purchase rows newest-first
   - assign stock tokens first, then order tokens
4) Allocate order tokens newest order first.

## Validation checks (run each time)
- Token count per SKU == demand + stock.
- No tokens created from purchase rows above the target.
- Recent orders use newest costs first.
- Token ledger and allocations are consistent with build summary.

## Files to inspect
- `out/token_ledger_live.csv`
- `out/token_allocations_live.csv`
- `out/token_november_build_summary.csv`
- `out/token_november_purchase_usage.csv`
- `out/token_november_order_shortfalls.csv`

## Notes
This build does **not** backdate purchases into extra tokens.
Only the newest required purchase rows are used for cost allocation.

## A2-T2AC-TW3L Check (expected)
- Orders since 2025-11-01: 513
- Stock to cover: 62 available + 5 FC processing + 120 inbound = 187
- Target tokens: 700

Preview output (bottom-up, cost allocation only):
- `out/analysis_reports/a2_t2ac_tw3l_token_usage_preview.csv`

Latest run check (2026-01-24):
- Inventory feed for A2-T2AC-TW3L: available 62, inbound_shipped 120, reserved_processing 4
- Target tokens: 513 + 186 = 699
- Ledger: 699 tokens (513 allocated, 186 available)
