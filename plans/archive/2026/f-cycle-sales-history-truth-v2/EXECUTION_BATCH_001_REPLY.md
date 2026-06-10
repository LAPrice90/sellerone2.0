# Execution Batch 001 Reply

## Status
- Complete / Partial / Failed:
  - complete
- Checked against:
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_001.md`

## Summary of changes
- Files changed:
  - `scripts/flows/F/F071_build_backtest_input_view.py`
  - `tests/test_f071_build_backtest_input_view.py`
- Behavior changed:
  - F071 now enforces trusted demand basis for READY rows:
    - READY is allowed only when `demand_basis_source` is `bbp_last_completed_month` or `bbp_zero_history`.
    - Fallback sources (`bbp_recent_history_fallback`, `bbp_current_month_fallback`, `e_velocity_30d_fallback`, and related helper fallbacks) now force `manual_review` with reason `demand_basis_not_trusted_completed_month`.
  - F071 now blocks invalid trusted-basis edge cases:
    - `invalid_last_completed_demand_basis_units`
    - `invalid_zero_history_demand_basis_units`
  - F071 tests were updated to reflect trusted-basis gating while preserving existing mapping/cost behavior checks.
  - Batch outputs were rebuilt end-to-end (`F070` -> `F074`) and one-off audits (`F004`, `F005`) were regenerated for proof.

## Tests run
- Command:
  - `pytest tests/test_f004_build_bbp_sales_sample_audit.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f070_build_backtest_policy_snapshot.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py`
- Result:
  - pass (`42 passed`)

## Proof
- Row counts:
  - `feeder_backtest_input_view_live.csv`
    - rows: `1542`
    - ready rows: `300`
    - manual review rows: `1242`
    - ready demand basis sources:
      - `bbp_last_completed_month`: `281`
      - `bbp_zero_history`: `19`
  - `feeder_backtest_replay_daily_live.csv`
    - rows: `109330`
    - failure rows: `19863`
  - `feeder_backtest_summary_live.csv`
    - rows: `1542`
    - `decision_state`:
      - `manual_review`: `1242`
      - `fail`: `249`
      - `pass`: `51`
  - `history_maturity_state` (input view):
    - `full_year`: `1359`
    - `stable`: `146`
    - `developing`: `21`
    - `recent_only`: `16`
- Health rows:
  - `feeder_backtest_health.csv` rebuilt:
    - rows: `16`
    - status counts: `ok=15`, `warn=1`, `fail=0`
  - key checks now `ok`:
    - `f_backtest_health_staleness`
    - `f_backtest_demand_basis_integrity`
    - `f_backtest_price_qualified_demand_integrity`
    - `f_backtest_decision_floor_integrity`
    - `f_backtest_join_resolution`
- Output paths:
  - `out/systems/F/live/feeder_backtest_policy_live.csv`
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- Other evidence:
  - At least one listing where raw monthly units are discounted to zero due economics floor:
    - `seller_sku=1248401`, `asin=B000CBCVEK`
    - raw units: `1`
    - qualified units: `0`
    - reason: `market_below_break_even`

## Issues found
- `f_backtest_manual_review_share = warn`:
  - notes: `manual_review_share=0.8054`
  - this is expected after tightening READY to trusted completed-month demand basis only.
- sampled one-off audit remains open:
  - `f_backtest_bbp_sales_sample_audit_latest.csv` currently reports `mismatch_rows=18`.

## Next batch notes
- Remaining work:
  - reduce `manual_review_share` by refreshing legacy scrape evidence so more rows carry `bbp_last_completed_month` truth
  - investigate sampled audit mismatches and align audit criteria with current decision outputs and trusted-basis gating
- Risks discovered:
  - decision output is now floor-aligned and demand-truth safe, but commercial coverage is currently limited by missing trusted completed-month evidence on many listings
