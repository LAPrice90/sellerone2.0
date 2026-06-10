# F Cycle Backtest - Execution Batch 1 - Completion Reply

## Completion Decision
- Status: COMPLETE
- Checked against: `reference/Backtest Strategy Ideas/F_cycle_backtest_execution_batch_1.md`

## Scope Check Against Batch Tasks

### Task 1 - Deterministic ASIN Resolution
- Status: Complete
- Implemented:
  - Added resolver file: `config/f_backtest_asin_resolution.csv`
  - Updated script: `scripts/flows/F/F071_build_backtest_input_view.py`
  - Resolver behavior now applies `mapping_status=resolved_asin_match` when resolver row exists.
  - Unresolved future conflicts still stay as `multi_sku_asin_match` and manual review.
- Tests updated:
  - `tests/test_f071_build_backtest_input_view.py`
  - `tests/test_f074_build_backtest_health.py`
- Proof:
  - Resolver file exists with 4 ASIN decisions.
  - Post-run `mapping_status=multi_sku_asin_match` count: `0`
  - Post-run `mapping_status=resolved_asin_match` count: `4`
  - `f_backtest_join_resolution` is now `ok`.

### Task 2 - Calibration Review Artifact
- Status: Complete
- Updated script:
  - `scripts/one_off/F002_build_backtest_calibration_set.py`
- Added calibration fields:
  - `calibration_review_flag`
  - `calibration_review_reason`
  - `critical_amazon_recommendation_mismatch_flag`
- First-pass mismatch rule implemented:
  - `amazon_risk_level=critical` and recommendation in `Normal fit` or `Managed fit`.
- Tests updated:
  - `tests/test_f002_build_backtest_calibration_set.py`
- Proof:
  - `out/analysis_reports/f_backtest_calibration_set_latest.csv` includes new fields.
  - `critical_amazon_recommendation_mismatch_flag=1` count: `2`

### Task 3 - Backtest Sign-Off Guidebook
- Status: Complete
- Created guidebook:
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
- Includes:
  - purpose
  - policy/input/replay/summary/health roles
  - identity resolver rule
  - calibration mismatch review rule
  - rerun and proof checklist

### Task 4 - Full Backtest Rerun And Evidence Pack
- Status: Complete
- Rerun chain executed successfully:
  - `python -m scripts.flows.F.F070_build_backtest_policy_snapshot`
  - `python -m scripts.flows.F.F071_build_backtest_input_view`
  - `python -m scripts.flows.F.F072_run_backtest_replay`
  - `python -m scripts.flows.F.F073_build_backtest_summary`
  - `python -m scripts.flows.F.F074_build_backtest_health`
  - `python scripts/one_off/F002_build_backtest_calibration_set.py`

## Evidence Summary

### Output row counts
- `out/systems/F/live/feeder_backtest_policy_live.csv` -> `1`
- `out/systems/F/live/feeder_backtest_input_view_live.csv` -> `146`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv` -> `49840`
- `out/systems/F/live/feeder_backtest_summary_live.csv` -> `146`
- `out/systems/F/live/feeder_backtest_health.csv` -> `9`
- `out/analysis_reports/f_backtest_calibration_set_latest.csv` -> `18`

### Health result
Source: `out/systems/F/live/feeder_backtest_health.csv` (observed_utc `2026-04-10T14:13:58Z`)
- `f_backtest_policy_single_active_row` -> `ok`
- `f_backtest_input_view_schema` -> `ok`
- `f_backtest_replay_daily_schema` -> `ok`
- `f_backtest_summary_schema` -> `ok`
- `f_backtest_summary_row_coverage` -> `ok`
- `f_backtest_replay_row_coverage` -> `ok`
- `f_backtest_low_confidence_share` -> `ok`
- `f_backtest_manual_review_share` -> `ok`
- `f_backtest_join_resolution` -> `ok` (value `0`)

### Resolver file contents (proof)
Source: `config/f_backtest_asin_resolution.csv`
- B0009OAI1S -> SCS21060
- B000C214CO -> SCS23964
- B005G0YQDG -> SCS15675
- B09X15JF1L -> SCS62023

### Calibration mismatch proof
Source: `out/analysis_reports/f_backtest_calibration_set_latest.csv`
- `critical_amazon_recommendation_mismatch_flag=1` count: `2`
- Rows flagged:
  - `SCS61975 / B0000BV12J / Managed fit / critical`
  - `SCS22690 / B000JCDV5A / Normal fit / critical`

## Batch Test Pack Result
Exact pack from batch file executed.
- Result: `44 passed`
- Command used:
  - `pytest tests/test_f000_paths_and_schemas.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f002_build_backtest_calibration_set.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py`

## Files Changed For This Batch
- `config/f_backtest_asin_resolution.csv`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/one_off/F002_build_backtest_calibration_set.py`
- `tests/test_f071_build_backtest_input_view.py`
- `tests/test_f074_build_backtest_health.py`
- `tests/test_f002_build_backtest_calibration_set.py`
- `project_control/F_BACKTEST_V1_GUIDEBOOK.md`

## Final Batch Outcome
- Join-resolution WARN cleared: Yes
- Calibration mismatch flags added and visible: Yes
- Guidebook created: Yes
- Full rerun evidence captured: Yes
- Batch test pack passed: Yes
