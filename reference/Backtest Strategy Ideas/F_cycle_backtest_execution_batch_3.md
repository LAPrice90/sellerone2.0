# F Cycle Backtest - Execution Batch 3

## Purpose

This batch moves the backtest from:
- built
- calibrated
- sign-off ready

to:
- operator-usable inside the restock interface

This is the first real control-surface batch.

The goal is to give the operator a safe, simple way to:
- see the active backtest policy
- change the small allowed v1 settings
- rerun the backtest after a policy change
- review the latest flagged calibration rows

## Batch Goal

Build the v1 operator control surface for the F backtest.

This must stay simple.

The operator should be able to control only:
- `minimum_expected_profit_gbp`
- `entry_target_roi_pct`
- `working_floor_roi_pct`
- `exit_floor_roi_pct`
- `emergency_floor_roi_pct`

This batch is not for new model logic.

## Important Batch Rule

Do not change:
- replay math
- competition-share assumptions
- seasonality logic
- ceiling logic
- recommendation scoring

Only build:
- policy edit path
- safe apply path
- rerun path
- calibration review view

## Task 1 - Add Policy Update Inbox Contract

### Goal

Create a safe staged path for operator policy changes instead of editing the live policy file directly.

### Required implementation

Add a new F contract in:
- `scripts/flows/F/_schemas.py`

Recommended new file:
- `out/systems/F/inbox/feeder_backtest_policy_update_events.csv`

Recommended required columns:
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

Recommended optional columns:
- `decision_note`

### Required behavior

This file must be:
- append-only
- durable
- operator-safe

The operator UI should submit to this inbox.
The live policy file should not be edited directly from the UI.

### Tests to create or update

Update:
- `tests/test_f000_paths_and_schemas.py`

Create:
- `tests/test_f075_apply_backtest_policy_updates.py`

### Acceptance criteria

- new inbox contract exists
- schema test covers it
- inbox file can be created empty with schema

## Task 2 - Apply Policy Update Script

### Goal

Create one canonical script that reads the policy-update inbox, validates the latest approved event, and writes the active live policy file.

### Required implementation

Create:
- `scripts/flows/F/F075_apply_backtest_policy_updates.py`

### Required behavior

The script should:
- read `feeder_backtest_policy_update_events.csv`
- take the latest valid event
- validate the 5 editable policy values
- write one active row to:
  - `out/systems/F/live/feeder_backtest_policy_live.csv`

Validation rules for v1:
- all 5 values must be numeric
- `entry_target_roi_pct >= working_floor_roi_pct`
- `working_floor_roi_pct >= exit_floor_roi_pct`
- `exit_floor_roi_pct >= emergency_floor_roi_pct`
- no blank policy values

If validation fails:
- do not overwrite the live policy
- fail cleanly with reason

### Tests to create or update

Create:
- `tests/test_f075_apply_backtest_policy_updates.py`

Test coverage needed:
- valid inbox event updates live policy
- invalid ordering is rejected
- missing values are rejected
- latest valid event wins
- live policy file remains one active row

### Acceptance criteria

- policy update script exists
- live policy remains deterministic
- bad inbox events do not corrupt the active policy file

## Task 3 - Operator UI Policy Section

### Goal

Add a simple backtest settings section inside the existing restock operator UI.

### Required implementation

Update:
- `scripts/flows/O/O400_operator_ui.py`

### Required UI behavior

Show current live backtest policy values:
- minimum expected profit
- entry target ROI
- working floor ROI
- exit floor ROI
- emergency floor ROI

Allow operator to submit new values into:
- `feeder_backtest_policy_update_events.csv`

This should be:
- simple
- clearly labelled as backtest policy
- not mixed into unrelated restock controls

### V1 scope limit

Do not add:
- advanced sliders
- multi-policy comparison
- historical policy audit panel

Simple form is enough.

### Tests to create or update

Update:
- `tests/test_o_ui_operator_view.py`

Test coverage needed:
- current policy values render
- policy update submission writes inbox event
- form handles empty / invalid values safely

### Acceptance criteria

- operator can see active values
- operator can submit a new policy event
- event lands in the F inbox file with schema

## Task 4 - Backtest Refresh Runner

### Goal

Create one simple rerun entrypoint for the full backtest chain after a policy change.

### Required implementation

Create:
- `scripts/one_off/F003_refresh_backtest_after_policy_change.py`

### Required behavior

This script should run:

```powershell
python -m scripts.flows.F.F075_apply_backtest_policy_updates
python -m scripts.flows.F.F071_build_backtest_input_view
python -m scripts.flows.F.F072_run_backtest_replay
python -m scripts.flows.F.F073_build_backtest_summary
python -m scripts.flows.F.F074_build_backtest_health
python scripts/one_off/F002_build_backtest_calibration_set.py
```

Notes:
- do not rerun F070 unless needed for bootstrap or explicit policy reset
- this script is for controlled refresh after a policy update event

### Tests

No direct end-to-end unit test required if helper coverage is good.
But the script must be simple and readable.

### Acceptance criteria

- one refresh entrypoint exists
- it uses the canonical scripts in the correct order

## Task 5 - Calibration Review Panel In UI

### Goal

Expose the latest calibration review pack inside the operator UI so the flagged rows can be checked without going to the CSV directly.

### Required implementation

Update:
- `scripts/flows/O/O400_operator_ui.py`

### Required behavior

Show latest calibration rows from:
- `out/analysis_reports/f_backtest_calibration_set_latest.csv`

At minimum show:
- seller_sku
- asin
- recommendation
- amazon_risk_level
- market_viability_score
- exit_risk_score
- calibration_review_flag
- calibration_review_reason

### V1 rule

Read-only panel only.

No editing from this screen.

### Tests to create or update

Update:
- `tests/test_o_ui_operator_view.py`

Test coverage needed:
- latest calibration file loads
- flagged rows render
- empty file degrades gracefully

### Acceptance criteria

- operator can see flagged calibration rows in UI
- no crash when calibration file is missing

## Batch Test Pack

Run this exact pack after code changes:

```powershell
pytest tests/test_f000_paths_and_schemas.py tests/test_f075_apply_backtest_policy_updates.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f002_build_backtest_calibration_set.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py
```

## Manual Run Pack

Run this exact pack for proof:

```powershell
python -m scripts.flows.F.F075_apply_backtest_policy_updates
python scripts/one_off/F003_refresh_backtest_after_policy_change.py
```

If no new policy event is queued, prove that:
- the apply script exits safely
- the refresh script still completes or explains why it did not rerun

## Expected End State

This batch is complete when:
- operator can see the active backtest policy in the UI
- operator can submit a valid policy update event
- one canonical apply script writes the live policy safely
- one canonical refresh script reruns the backtest after policy change
- operator can view latest calibration flags in the UI
- test pack passes

## Not In This Batch

Do not do these here:
- UI redesign
- policy history analytics
- automatic policy optimisation
- changing any core backtest math

## Suggested Final Output Back To User

When this batch is done, the Codex response should include:
- what changed
- which files changed
- test results
- proof of UI policy event submission
- proof of policy application
- proof of refreshed backtest outputs
- proof of calibration panel rendering
