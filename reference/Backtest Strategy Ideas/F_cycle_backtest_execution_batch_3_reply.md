# F Cycle Backtest - Execution Batch 3 - Completion Reply

## Completion Decision
- Status: COMPLETE
- Checked against: `reference/Backtest Strategy Ideas/F_cycle_backtest_execution_batch_3.md`

## Scope Check Against Batch Tasks

### Task 1 - Add Policy Update Inbox Contract
- Status: Complete
- Updated file:
  - `scripts/flows/F/_schemas.py`
- Implementation:
  - Added new append-only F inbox contract:
    - `out/systems/F/inbox/feeder_backtest_policy_update_events.csv`
  - Added required columns:
    - `event_utc`
    - `event_id`
    - `policy_id`
    - `action`
    - `minimum_expected_profit_gbp`
    - `entry_target_roi_pct`
    - `working_floor_roi_pct`
    - `exit_floor_roi_pct`
    - `emergency_floor_roi_pct`
    - `actor`
    - `source_reference`
  - Added optional column:
    - `decision_note`
- Tests updated:
  - `tests/test_f000_paths_and_schemas.py`
- Acceptance evidence:
  - Contract is present and registered in F schema contract list.
  - Schema tests pass with new contract present.

### Task 2 - Apply Policy Update Script
- Status: Complete
- Created file:
  - `scripts/flows/F/F075_apply_backtest_policy_updates.py`
- Implementation:
  - Reads inbox events from `feeder_backtest_policy_update_events.csv`
  - Selects the latest valid event (newest-first scan with validation)
  - Validates editable controls as numeric:
    - `minimum_expected_profit_gbp`
    - `entry_target_roi_pct`
    - `working_floor_roi_pct`
    - `exit_floor_roi_pct`
    - `emergency_floor_roi_pct`
  - Enforces ordering rule:
    - `entry_target_roi_pct >= working_floor_roi_pct >= exit_floor_roi_pct >= emergency_floor_roi_pct`
  - Writes exactly one active row to:
    - `out/systems/F/live/feeder_backtest_policy_live.csv`
  - Failure behavior:
    - Invalid or blank events do not overwrite live policy.
    - Script fails cleanly when no valid event exists.
  - Safe no-event behavior:
    - Emits `no_change` if inbox file is absent/empty.
- Tests created:
  - `tests/test_f075_apply_backtest_policy_updates.py`
- Coverage delivered:
  - valid inbox event updates live policy
  - invalid ordering rejected
  - missing values rejected
  - latest valid event wins
  - live policy remains one active row

### Task 3 - Operator UI Policy Section
- Status: Complete
- Updated file:
  - `scripts/flows/O/O400_operator_ui.py`
- Implementation:
  - Added backtest policy control section in the Reorder Input tab.
  - Displays current active live policy values.
  - Adds form submission path to append events into:
    - `out/systems/F/inbox/feeder_backtest_policy_update_events.csv`
  - Added UI-side validation for empty/non-numeric values and ROI ordering.
  - Keeps write path inbox-only (no direct live policy write from UI).
- Tests updated:
  - `tests/test_o_ui_operator_view.py`
- Coverage delivered:
  - current live policy values load/render path
  - policy event submission writes F inbox event
  - validation handles empty / invalid values safely

### Task 4 - Backtest Refresh Runner
- Status: Complete
- Created file:
  - `scripts/one_off/F003_refresh_backtest_after_policy_change.py`
- Implementation:
  - Runs canonical sequence:
    - `python -m scripts.flows.F.F075_apply_backtest_policy_updates`
    - `python -m scripts.flows.F.F071_build_backtest_input_view`
    - `python -m scripts.flows.F.F072_run_backtest_replay`
    - `python -m scripts.flows.F.F073_build_backtest_summary`
    - `python -m scripts.flows.F.F074_build_backtest_health`
    - `python scripts/one_off/F002_build_backtest_calibration_set.py`
  - Emits structured success/failure output with per-step return code and log tails.

### Task 5 - Calibration Review Panel In UI
- Status: Complete
- Updated file:
  - `scripts/flows/O/O400_operator_ui.py`
- Implementation:
  - Added read-only calibration review section.
  - Loads:
    - `out/analysis_reports/f_backtest_calibration_set_latest.csv`
  - Displays required review columns:
    - `seller_sku`
    - `asin`
    - `recommendation`
    - `amazon_risk_level`
    - `market_viability_score`
    - `exit_risk_score`
    - `calibration_review_flag`
    - `calibration_review_reason`
  - Shows flagged rows and full latest review table.
  - Missing/empty file behavior degrades safely without crash.
- Tests updated:
  - `tests/test_o_ui_operator_view.py`
- Coverage delivered:
  - latest calibration file loads
  - flagged-row selection works
  - missing file returns safe empty view

## Batch Test Pack Result
- Status: Complete
- Command run:
  - `pytest tests/test_f000_paths_and_schemas.py tests/test_f075_apply_backtest_policy_updates.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f002_build_backtest_calibration_set.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py`
- Result:
  - `56 passed`

## Manual Run Pack Result
- Status: Complete
- Command 1:
  - `python -m scripts.flows.F.F075_apply_backtest_policy_updates`
- Result:
  - safe no-op with `no_policy_update_events` (no live event queued)

- Command 2:
  - `python scripts/one_off/F003_refresh_backtest_after_policy_change.py`
- Result:
  - full refresh chain completed successfully in required order
  - `F075` safe no-op
  - `F071` success: `146` rows (`143` ready / `3` manual review)
  - `F072` success: `49840` rows
  - `F073` success: `146` rows (`143` ready / `3` manual review)
  - `F074` success: `9` checks all `ok`
  - `F002` success: latest calibration rebuilt (`18` rows)

## Evidence Summary

### Files changed in this batch
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/F075_apply_backtest_policy_updates.py`
- `scripts/flows/O/O400_operator_ui.py`
- `scripts/one_off/F003_refresh_backtest_after_policy_change.py`
- `tests/test_f000_paths_and_schemas.py`
- `tests/test_f075_apply_backtest_policy_updates.py`
- `tests/test_o_ui_operator_view.py`

### Current output row counts
- `out/systems/F/inbox/feeder_backtest_policy_update_events.csv` -> missing (no event submitted yet in live repo state)
- `out/systems/F/live/feeder_backtest_policy_live.csv` -> `1`
- `out/systems/F/live/feeder_backtest_input_view_live.csv` -> `146`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv` -> `49840`
- `out/systems/F/live/feeder_backtest_summary_live.csv` -> `146`
- `out/systems/F/live/feeder_backtest_health.csv` -> `9`
- `out/analysis_reports/f_backtest_calibration_set_latest.csv` -> `18`

### Final health summary
Source: `out/systems/F/live/feeder_backtest_health.csv` (observed_utc `2026-04-10T15:15:27Z`)
- `f_backtest_policy_single_active_row` -> `ok`
- `f_backtest_input_view_schema` -> `ok`
- `f_backtest_replay_daily_schema` -> `ok`
- `f_backtest_summary_schema` -> `ok`
- `f_backtest_summary_row_coverage` -> `ok`
- `f_backtest_replay_row_coverage` -> `ok`
- `f_backtest_low_confidence_share` -> `ok`
- `f_backtest_manual_review_share` -> `ok`
- `f_backtest_join_resolution` -> `ok`

### UI policy event submission proof
- Automated proof exists in test:
  - `tests/test_o_ui_operator_view.py::test_o_ui_policy_update_submission_writes_f_inbox_event`
- The test verifies:
  - UI submission function writes inbox event row
  - event contains policy values, actor, source reference, and decision note

### Policy application proof
- Automated proof exists in test:
  - `tests/test_f075_apply_backtest_policy_updates.py::test_f075_valid_event_updates_live_policy`
- Manual live proof:
  - `F075` exits safely with `no_change` when no queued event exists

### Refreshed backtest output proof
- `F003` refresh runner executed successfully and rebuilt:
  - input view
  - replay daily
  - summary
  - health
  - calibration set

### Calibration panel rendering proof
- Automated proof exists in tests:
  - `tests/test_o_ui_operator_view.py::test_o_ui_calibration_loader_reads_latest_and_selects_flagged_rows`
  - `tests/test_o_ui_operator_view.py::test_o_ui_calibration_loader_handles_missing_file_gracefully`

## Final Batch Outcome
- Operator can see active backtest policy values in UI: Yes
- Operator can submit policy update events to F inbox: Yes
- Canonical apply script exists and safely updates live policy: Yes
- Canonical refresh entrypoint exists and runs required chain: Yes
- Operator can view latest calibration flags/rows in UI: Yes
- Batch test pack passes: Yes
