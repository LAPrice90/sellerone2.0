# E Cycle Phases

## Phase 0 - Foundations
- Confirm inputs exist and are fresh.
- Add schema checks to A015 for all E outputs.
- Define stock-out aware velocity rule.

## Phase 1 - Core outputs
- Build sku_sales_velocity.csv
- Build sku_roi_snapshot.csv
- Build sku_restock_signals.csv
- Build sku_performance_summary.csv

## Phase 2 - Publish + gate
- Stage E outputs locally.
- Publish only when A015 shows no FAIL.
- Keep last 3 snapshots for rollback.

## Phase 3 - Quality guardrails
- Idempotent reruns (same input, same output).
- Add regression fixtures for past bugs.
- Add alert if any SKU flips to negative ROI.

## Phase 4 - Daily ops
- Run after B cycle daily.
- Review E alerts before any strategy changes.
