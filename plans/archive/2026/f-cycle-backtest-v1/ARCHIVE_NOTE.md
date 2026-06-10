# Archive Note

## Status
- Archived on 2026-04-14.

## Why this plan was archived
- The active problem is no longer just "backtest the old F policy."
- The business need became broader and clearer:
  - separate raw sales from sales available to us at our price
  - detect seasonality without over-trusting one or two strong months
  - judge recent performance versus full-history context
  - apply a real monthly profit floor
  - leave a learning trail after purchase decisions
- That required a new active planning spine rather than more batches inside the older backtest-only frame.

## What this archive still preserves
- Completed build history from the earlier backtest work
- Batch 008 user-alignment notes
- Batch 009 demand-basis cleanup scope and proof history
- Reference implementation context for current F backtest outputs

## Work carried forward
- Successor plan at archive time, later archived:
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/`
- Main carry-forward items:
  - price-qualified monthly demand
  - seasonality and stability classification
  - recent-performance classification
  - `GBP 20` monthly profit floor enforcement
  - sampled-ASIN validation path
  - post-purchase 90-day learning loop

## Known unresolved state at archive time
- `f_backtest_demand_basis_integrity = warn`
- `f_backtest_join_resolution = warn`
- latest live files were newer than the current health file, so proof state was partly stale
