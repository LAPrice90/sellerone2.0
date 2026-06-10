# F Cycle Backtest - Execution Batch 7 - Completion Reply

## Completion Decision
- Status: COMPLETE
- Checked against: `plans/active/f-cycle-backtest-v1/EXECUTION_BATCH_007.md`

## Scope Check Against Batch Tasks

### Task 1 - Scenario Share Governance In Replay
- Status: Complete
- Updated file:
  - `scripts/flows/F/F072_run_backtest_replay.py`
- Delivered:
  - scenario share caps for shared scenarios
  - replay reason tags for sparse prior-blend sourcing and cap application
  - governed-share path applied before non-price-match haircut logic

### Task 2 - Summary Basis And Share Governance Tags
- Status: Complete
- Updated file:
  - `scripts/flows/F/F073_build_backtest_summary.py`
- Delivered:
  - `share_assumption_basis` updated to governed-share model label
  - share-governance replay tags carried into ready summary reason codes

### Task 3 - Prior Dependency Health Check
- Status: Complete
- Updated file:
  - `scripts/flows/F/F074_build_backtest_health.py`
- Delivered:
  - `f_backtest_share_prior_dependency` check
  - warn threshold and scoped notes for prior-dependent replay concentration

### Task 4 - Scoped Tests And Proof Rerun
- Status: Complete
- Tests run:
  - `pytest tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py`
  - result: `19 passed`
- Rerun chain executed:
  - `F071 -> F072 -> F073 -> F074 -> F002`

## Evidence Summary

### Output counts after rerun
- `feeder_backtest_input_view_live.csv` rows: `355`
- `feeder_backtest_replay_daily_live.csv` rows: `108388`
- `feeder_backtest_summary_live.csv` rows: `355`
- `feeder_backtest_health.csv` rows: `12`

### Backtest health status
- status counts: `ok=12`
- key checks:
  - `f_backtest_share_prior_dependency` -> `ok`
    - `prior_dependency_rows=365`
    - `replay_rows=108388`
    - `sparse_blend_rows=365`
  - `f_backtest_sales_share_validity` -> `ok`
    - `missing=0`
    - `amazon_rows=45420`
    - `high_amazon_share_rows=0`
  - `f_backtest_attribution_confidence_share` -> `ok`
    - `ready_rows=304`
    - `attribution_warn_rows=13`

### Share-governance tag evidence
- replay rows with `share_governance_cap_applied`: `44284`
- replay rows with `share_source_sparse_asin_blend`: `365`
- replay rows with share not equal to `50` or `100`: `82241`
- distinct replay `sales_share_pct` values: `286`
- summary rows carrying `share_governance_cap_applied`: `235`
- summary rows carrying `share_source_sparse_asin_blend`: `112`
- summary rows with basis `v1_measured_share_with_prior_and_scenario_caps`: `355`

### Calibration pack status
- latest calibration rows: `18`
- blockers: none

### Global health snapshot check
- `out/system_health_checklist.csv` rows with `warn` or `fail`: `0`

## Final Batch Outcome
- Replay share assumptions are now governed and tagged: Yes
- Summary reflects governed-share basis and reason tags: Yes
- Prior dependency health visibility is in place and currently `ok`: Yes
- Scoped tests and proof rerun completed successfully: Yes
