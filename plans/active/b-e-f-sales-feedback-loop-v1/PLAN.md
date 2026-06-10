# Plan

## Goal
- Final outcome:
  - make B and E the automatic actual-sales truth source for F feedback
  - remove manual actuals entry from the normal learning path
  - let the user review decision examples instead of moving data around
  - keep finalized and provisional truth separate all the way through

## Non-goals
- Do not:
  - write to Google Sheets
  - rewrite the local DB
  - treat L1 economics as final truth
  - hide freshness lag by downstream averaging
  - promote any new builder into a live loop before one-off proof is clean

## Current state
- What already exists:
  - B collects multi-level financial events and builds `out/order_master.csv`
  - B builds `out/order_ledger_fx.csv`
  - E builds:
    - `out/sku_roi_snapshot.csv`
    - `out/sales_truth_sku_30d_latest.csv`
    - `out/sales_truth_reconciliation_latest.csv`
    - `out/sku_daily_sales_truth_latest.csv`
    - `out/sku_performance_summary.csv`
  - F builds decision snapshots in:
    - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - F learning pack exists, but still depends on manual actuals input shape
- What is broken or missing:
  - truth freshness is not guaranteed from B into E outputs
  - no explicit bridge from operational ASIN/SKU to F learning rows
  - no automatic actuals ingestion into F learning
  - current supplier-scan universe is not the same as the operational catalog universe

## Target state
- one explicit actual-sales foundation mart exists with:
  - freshness timestamps
  - source state
  - finalized/provisional split
  - bridge status
- one explicit operational replay seed exists so F can study the products we really sell
- one automatic actuals builder populates 30d, 60d, and 90d result fields for F learning
- one operator review pack explains:
  - where F was right
  - where F was wrong
  - whether the mistake was demand, price, seasonality, or operational timing

## Systems touched
- Flow(s):
  - B read/write in later batches only if freshness repair is needed
  - E primary for truth derivation outputs
  - F primary for learning and review outputs
  - A health only through existing downstream proof artifacts, not ad-hoc runs
- Shared dependencies:
  - `out/financial_events_level1.csv`
  - `out/financial_events_level3_official.csv`
  - `out/order_master.csv`
  - `out/order_ledger_fx.csv`
  - `out/sku_daily_sales_truth_latest.csv`
  - `out/sales_truth_sku_30d_latest.csv`
  - `out/sku_performance_summary.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/listing_offer_history.csv`
  - `out/listing_offer_snapshot_latest.csv`

## Output ownership
| Item | Planned owner | Input or output | Path | Notes |
|---|---|---|---|---|
| Sales truth foundation | `scripts/one_off/BEF000_build_sales_truth_foundation.py` | output | `out/analysis_reports/bef_sales_truth_foundation_latest.csv` | one row per operational SKU with freshness and trust fields |
| Operational ASIN bridge | `scripts/one_off/BEF001_build_operational_feedback_seed.py` | output | `out/analysis_reports/bef_operational_feedback_seed_latest.csv` | maps operational ASIN and SKU into replay scope |
| Feedback health | `scripts/one_off/BEF000_build_sales_truth_foundation.py` | output | `out/analysis_reports/bef_sales_feedback_health_latest.csv` | freshness, bridge, and stale-state checks |
| Auto actuals pack | `scripts/one_off/BEF002_build_sales_feedback_actuals.py` | output | `out/analysis_reports/f_sales_history_learning_actuals_latest.csv` | automatic replacement for manual normal-use actuals entry |
| Learning review pack | existing `F012` plus `BEF002` | output | `out/analysis_reports/f_sales_history_learning_review_latest.csv` | expected vs actual learning rows |
| Decision example pack | `scripts/one_off/BEF003_build_sales_feedback_examples.py` | output | `out/analysis_reports/bef_sales_feedback_examples_latest.csv` | user-facing review examples only |
| Feedback health checks | `scripts/one_off/BEF004_build_sales_feedback_health.py` | output | `out/analysis_reports/bef_sales_feedback_health_latest.csv` | schema, freshness, and bridge truth |

## Trust rules
- Finalized sales and profit truth:
  - use `sku_daily_sales_truth_latest.csv` rows where `source_state=finalized_ledger`
- Provisional recent truth:
  - use `sku_daily_sales_truth_latest.csv` rows where `source_state=provisional_order_master`
- Reconciliation-only outputs:
  - `sales_truth_sku_30d_latest.csv`
  - `sales_truth_reconciliation_latest.csv`
- Operational summary outputs:
  - `sku_performance_summary.csv` is allowed for reference and ranking, not as the only actuals source
- F learning:
  - must consume automated actuals output, not a hand-filled template, once Batch 001 is complete

## Phase list

### Phase 0 - truth freshness and bridge foundation
- build the explicit actual-sales foundation mart
- measure `order_master -> order_ledger_fx -> E output` freshness lag
- build operational replay seed from current selling/catalog universe
- make unresolved bridge rows explicit

### Phase 1 - automatic actuals for F learning
- use foundation and bridge outputs to build:
  - 30d actual units and profit
  - 60d actual units and profit
  - 90d actual units and profit
- populate `f_sales_history_learning_actuals_latest.csv` automatically

### Phase 2 - operator example pack
- create example rows for:
  - right call
  - demand too high
  - demand too low
  - price assumption wrong
  - seasonality misread
  - operational timing mismatch

### Phase 3 - guarded automation
- wire the one-off sequence into a safe scheduled path
- keep it health-gated
- do not auto-promote to loop ownership without proof

## Success monitoring
- freshness lag between `order_master.csv` and `order_ledger_fx.csv` is explicit
- finalized versus provisional row counts are explicit
- unresolved bridge rows are explicit
- automatic actuals fill rate is explicit
- example pack row counts by outcome class are explicit
- user task is reduced to example review only

## Proof rules
- What counts as code fix applied:
  - active plan exists
  - study report exists
  - coding plan exists
  - later one-off builders and tests exist
- What counts as isolated verification passed:
  - targeted pytest passes
  - one-off builders run successfully
  - output row counts and freshness fields are present
- What counts as live loop verification confirmed:
  - not applicable until later promotion phase
  - this plan starts one-off first
