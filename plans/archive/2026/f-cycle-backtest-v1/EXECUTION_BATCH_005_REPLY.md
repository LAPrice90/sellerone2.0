# F Cycle Backtest - Execution Batch 5 - Completion Reply

## Completion Decision
- Status: COMPLETE
- Checked against: `plans/active/f-cycle-backtest-v1/EXECUTION_BATCH_005.md`

## Scope Check Against Batch Tasks

### Task 1 - Measured Share Estimation In Replay
- Status: Complete
- Updated file:
  - `scripts/flows/F/F072_run_backtest_replay.py`
- Delivered:
  - measured scenario share signals from observed chart history
  - per-ASIN scenario rate blending with global prior
  - safe fallback path when measured coverage is missing

### Task 2 - Replay Tests For Measured Share
- Status: Complete
- Updated file:
  - `tests/test_f072_run_backtest_replay.py`
- Added coverage:
  - Amazon-owned Buy Box scenario share becomes `0`
  - sparse scenario sample uses prior blending
  - core replay path still works

### Task 3 - Sales-Share Health Check
- Status: Complete
- Updated files:
  - `scripts/flows/F/F074_build_backtest_health.py`
  - `tests/test_f074_build_backtest_health.py`
- Added check:
  - `f_backtest_sales_share_validity`

### Task 4 - Proof Rerun Chain
- Status: Complete
- Commands run:
  - `python -m scripts.flows.F.F071_build_backtest_input_view`
  - `python -m scripts.flows.F.F072_run_backtest_replay`
  - `python -m scripts.flows.F.F073_build_backtest_summary`
  - `python -m scripts.flows.F.F074_build_backtest_health`
  - `python scripts/one_off/F002_build_backtest_calibration_set.py`

## Test Result

- Command:
  - `pytest tests/test_f072_run_backtest_replay.py tests/test_f074_build_backtest_health.py`
- Result:
  - `10 passed`

## Evidence Summary

### Replay and summary outputs after rerun
- `feeder_backtest_input_view_live.csv` rows: `347`
- `feeder_backtest_replay_daily_live.csv` rows: `119179`
- `feeder_backtest_summary_live.csv` rows: `347`

### Backtest health after rerun
- Source: `out/systems/F/live/feeder_backtest_health.csv`
- rows: `10`
- status counts: `ok=10`
- new check:
  - `f_backtest_sales_share_validity` -> `ok`

### Measured-share evidence
- replay rows with `sales_share_pct` not equal to `50` or `100`: `52369`
- distinct replay `sales_share_pct` values: `377`
- scenario medians:
  - `sharing_with_amazon`: `30.294908`
  - `sharing_with_amazon_and_fba`: `48.934859`
  - `sharing_with_fba`: `100`
  - `solo_or_no_meaningful_competition`: `100`

### Calibration proof
- `f_backtest_calibration_set_latest.csv` rows: `18`
- latest build status: success with no blockers

## Final Batch Outcome
- Provisional fixed-share logic replaced by measured scenario rates: Yes
- New share-validity health check added and passing: Yes
- Scoped tests passing: Yes
- Affected F outputs rebuilt with fresh evidence: Yes
