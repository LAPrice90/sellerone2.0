# F Cycle Backtest - Execution Batch 2 - Completion Reply

## Completion Decision
- Status: COMPLETE
- Checked against: `reference/Backtest Strategy Ideas/F_cycle_backtest_execution_batch_2.md`

## Scope Check Against Batch Tasks

### Task 1 - Lock Critical Amazon Recommendation Cap
- Status: Complete
- Updated file:
  - `scripts/flows/F/F073_build_backtest_summary.py`
- Implementation:
  - Added governance cap so `summary_status=ready` and `amazon_risk_level=critical` cannot output:
    - `Normal fit`
    - `Managed fit`
  - Capped output for those rows to `Exit-only`.
  - Non-critical rows continue through existing recommendation logic unchanged.
- Tests updated:
  - `tests/test_f073_build_backtest_summary.py`
  - `tests/test_f002_build_backtest_calibration_set.py`
- Proof:
  - Post-rerun full-summary count where:
    - `amazon_risk_level=critical`
    - recommendation in (`Normal fit`,`Managed fit`)
  - Result: `0`

### Task 2 - Rerun Full F Backtest Chain
- Status: Complete
- Executed:
  - `python -m scripts.flows.F.F070_build_backtest_policy_snapshot`
  - `python -m scripts.flows.F.F071_build_backtest_input_view`
  - `python -m scripts.flows.F.F072_run_backtest_replay`
  - `python -m scripts.flows.F.F073_build_backtest_summary`
  - `python -m scripts.flows.F.F074_build_backtest_health`
  - `python scripts/one_off/F002_build_backtest_calibration_set.py`

### Task 3 - Full Test Pack
- Status: Complete
- Pack result: `46 passed`
- Command used:
  - `pytest tests/test_f000_paths_and_schemas.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f002_build_backtest_calibration_set.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py`

### Task 4 - Final Sign-Off Evidence
- Status: Complete
- Evidence provided below:
  - changed files
  - test results
  - final health summary
  - final mismatch count
  - final critical-Amazon governance count
  - recommendation breakdown counts
  - sign-off readiness

## Evidence Summary

### Changed files in this batch
- `scripts/flows/F/F073_build_backtest_summary.py`
- `tests/test_f073_build_backtest_summary.py`
- `tests/test_f002_build_backtest_calibration_set.py`

### Output row counts
- `out/systems/F/live/feeder_backtest_policy_live.csv` -> `1`
- `out/systems/F/live/feeder_backtest_input_view_live.csv` -> `146`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv` -> `49840`
- `out/systems/F/live/feeder_backtest_summary_live.csv` -> `146`
- `out/systems/F/live/feeder_backtest_health.csv` -> `9`
- `out/analysis_reports/f_backtest_calibration_set_latest.csv` -> `18`

### Final health summary
Source: `out/systems/F/live/feeder_backtest_health.csv` (observed_utc `2026-04-10T14:40:41Z`)
- `f_backtest_policy_single_active_row` -> `ok`
- `f_backtest_input_view_schema` -> `ok`
- `f_backtest_replay_daily_schema` -> `ok`
- `f_backtest_summary_schema` -> `ok`
- `f_backtest_summary_row_coverage` -> `ok`
- `f_backtest_replay_row_coverage` -> `ok`
- `f_backtest_low_confidence_share` -> `ok`
- `f_backtest_manual_review_share` -> `ok`
- `f_backtest_join_resolution` -> `ok`

### Final mismatch and governance counts
- Calibration mismatch count (`critical_amazon_recommendation_mismatch_flag=1` in latest calibration set): `0`
- Full-summary governance count (`critical` + `ready` + `Normal fit/Managed fit`): `0`

### Final recommendation breakdown counts
From `out/systems/F/live/feeder_backtest_summary_live.csv`:
- `Avoid` -> `78`
- `Exit-only` -> `36`
- `Managed fit` -> `5`
- `Manual review` -> `3`
- `Normal fit` -> `24`

## Final Batch Outcome
- Critical Amazon recommendation cap active: Yes
- Targeted tests passed: Yes
- Full pack passed: Yes
- Health remains fully `ok`: Yes
- Calibration mismatch count: `0`
- Critical-Amazon rows still returning `Normal fit` or `Managed fit`: `0`
- V1 backtest ready for sign-off: Yes
