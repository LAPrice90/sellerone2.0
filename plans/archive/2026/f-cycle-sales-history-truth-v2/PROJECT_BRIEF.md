# Project Brief

## Ticket
- Ticket name:
  - F cycle sales history truth v2
- Date opened:
  - 2026-04-14
- Owner:
  - Codex, with user sign-off on commercial rules

## Business problem
- What is hurting today?
  - The current F backtest can read BBP sales history more truthfully than before, but it still does not answer the business question cleanly.
  - We can still overstate expected sales and profit by treating raw observed market sales as if they were all available to us at our price.
  - Seasonality, recent performance, and price-qualified demand are not yet separated clearly enough.
- What decision or process is blocked?
  - We do not yet have a trustworthy answer to:
    - if I buy this now, how many sales should I expect at our economics
    - is the item seasonal or just spiky
    - is the listing stable, underperforming, or overperforming recently
    - is the expected monthly profit good enough to justify buying

## Goal
- What should exist when this is done?
  - One active F planning path that turns BBP sales history and price history into a business-first decision model.
  - The model must separate:
    - raw observed market demand
    - addressable demand at our price and share assumptions
    - seasonality and history stability
    - recent performance versus baseline
    - confidence and explicit fail/manual-review reasons
  - The system must also leave room for 90-day post-purchase learning so assumptions can be checked against reality.

## Why now
- Why is this worth doing now?
  - Guided ASIN review exposed that the important mistake is not just chart extraction.
  - The deeper problem is decision logic:
    - completed month versus current month
    - raw sales versus sales we could actually participate in
    - one strong month versus repeatable demand
    - profit above break-even versus profit worth the effort
  - User-aligned commercial rule already exists:
    - expected monthly profit below `GBP 20` should normally fail
  - Current F health is also not fully trusted:
    - `f_backtest_demand_basis_integrity = warn`
    - `f_backtest_join_resolution = warn`

## Constraints
- Existing system boundaries:
  - Build on the current F evidence and backtest pipeline where possible.
  - Keep one-off audit scripts out of daily loops.
  - Do not change Google Sheets.
  - Do not change local DB state to match planning assumptions.
- Out of scope:
  - Rewriting H runtime logic
  - Building a full optimizer
  - Solving every seller-attribution edge case before the demand model is usable
  - Manual per-ASIN exception lists as the primary decision engine
- Approval-sensitive areas:
  - Monthly profit floor changes
  - Any decision rule that changes buy/pass/fail policy
  - Any future move from planning outputs into live operator surfaces

## Definition of success
- Observable result 1:
  - Old fragmented active backtest plan is archived and replaced by one clean active plan.
- Observable result 2:
  - New decision model states exactly how much history is recognized, how seasonality is detected, how recent performance is read, and how price-qualified demand is calculated.
- Observable result 3:
  - Next implementation batches are ordered clearly from data truth to decision output to post-purchase learning.

## Reference material
- Research notes:
  - `reference/Backtest Strategy Ideas/finalisation1.md`
  - `reference/Backtest Strategy Ideas/patterns.md`
  - `reference/Backtest Strategy Ideas/ExtendedProThinking.md`
  - `reference/Backtest Strategy Ideas/deepResearch.md`
- Related repo files:
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
- Prior tickets or plans:
  - archived `f-cycle-backtest-v1`
