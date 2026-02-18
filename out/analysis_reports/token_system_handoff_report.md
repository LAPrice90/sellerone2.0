# Token System Handoff Report (Nov‑Anchored Model)

Last updated: 2026-01-20

## Objective
Build a deterministic, November‑anchored token system where:
- Tokens = net demand since 2025‑11‑01 (UK) + current sellable stock.
- Purchases are only used to source costs for those tokens (newest first).
- Units beyond the target are ignored by design.

## Core Rules (Locked)
- **Demand** = orders since 2025‑11‑01 minus refunds (net shipped proxy).
- **Stock** = `inventory_summaries.csv` `available` only (sellable).
- **Purchases**:
  - `Ordered` = supply capacity for sales tokens.
  - `Sent to FBA` = stock‑eligible capacity (for stock tokens).
- **Allocation**:
  - Build tokens from newest purchases working backward.
  - Apply to stock first (Sent to FBA cap).
  - Allocate orders newest‑first.
- **SKU mismatches** = hard errors; no auto‑normalization.

## New/Updated Scripts
- `scripts/B024_build_tokens_november_anchor.py`
  - Builds tokens from CSVs only.
  - Outputs:
    - `out/token_ledger_live.csv`
    - `out/token_allocations_live.csv`
    - `out/token_november_build_summary.csv`
    - `out/token_november_purchase_usage.csv`
    - `out/token_november_order_shortfalls.csv`
- `scripts/B025_build_token_cogs_ledger.py`
  - Builds **unit‑level** token COGS ledger.
  - Output: `out/token_cogs_ledger.csv`
- `scripts/one_off/T023_rebuild_level1_from_archive.py`
  - Now **unit‑level** rows with token_id + COGS per unit.
  - Adds columns: `token_id`, `token_cost`, `token_currency`, `token_source`.
- `scripts/B010_build_token_ops_outputs.py`
  - Uses `token_cogs_ledger.csv` as primary COGS source.
  - Output: `out/order_cogs_from_tokens.csv`
- `scripts/B026_run_token_cycle.py`
  - One‑shot pipeline:
    - B024 → B025 → rebuild_level1 → Order_Master → tests → checklist.

## Automation (B‑cycle)
`scripts/run_B_cycle.py` now includes P&L:
- Added `D001_build_pnl_daily.py` at the end.
- P&L uses `out/order_cogs_from_tokens.csv` which is now driven by token ledger.

## Current Status (from latest run)
From `out/token_november_build_summary.csv`:
- SKUs: 143
- Net demand: 6,033 units
- Stock needed: 2,693 units
- Target tokens: 8,726
- Tokens created: 8,726
- Orders allocated: 6,033
- Shortfalls: 0

From `out/token_november_purchase_usage.csv`:
- Purchase rows used: 172
- Used for stock: 2,693
- Used for orders: 6,033
- Unused purchases: 4,650 (expected by design)

## Key Outputs for Review
- Token ledger: `out/token_ledger_live.csv`
- Token allocations: `out/token_allocations_live.csv`
- Token COGS ledger (unit‑level): `out/token_cogs_ledger.csv`
- Order COGS rollup: `out/order_cogs_from_tokens.csv`
- Level 1 (unit‑level): `out/financial_events_level1.csv`
- Order master: `out/order_master.csv`
- Daily P&L: `out/pnl_daily.csv`

## Known Gaps / TODO
- B‑cycle does **not** yet run:
  - `B024_build_tokens_november_anchor.py`
  - `B025_build_token_cogs_ledger.py`
  If we want full automation, add those ahead of allocation.
- Refunds are used for net demand only if `financial_events_refunds_official.csv` is present.
- SKU mismatch reporting is not yet automated.

## Questions for Sign‑Off
1) Confirm demand definition (net orders since 2025‑11‑01 minus refunds).
2) Confirm stock definition (`available` only).
3) Confirm use of `Sent to FBA` as stock‑eligible cap.
4) Confirm newest‑first cost allocation for sales + stock.

