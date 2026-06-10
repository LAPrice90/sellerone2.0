# F Cycle Backtest - Execution Batch 2

## Purpose

This file defines the next Codex execution batch.

This is a closeout batch, not a research batch.

The aim is to take the current backtest from:
- technically stable
- identity-resolved
- calibration-visible

to:
- commercially locked for v1
- rerun with final evidence
- ready for sign-off

## Batch Goal

Fix the remaining recommendation-governance issue in the backtest:
- rows with `amazon_risk_level = critical` still appearing as `Normal fit` or `Managed fit`

This batch should:
- lock the recommendation-cap rule
- update tests
- rerun the full F backtest chain
- rerun the calibration set
- run the full F/O backtest test pack
- return final evidence for sign-off

## Current Starting State

The current backtest pipeline already exists and is operational:
- `scripts/flows/F/F070_build_backtest_policy_snapshot.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/one_off/F002_build_backtest_calibration_set.py`

Current known position:
- join-resolution is now cleared
- backtest health is currently all `ok`
- calibration mismatch fields exist
- current calibration mismatch count is `2`

The currently flagged rows are:
- `SCS61975 / B0000BV12J / Managed fit / critical`
- `SCS22690 / B000JCDV5A / Normal fit / critical`

## Important Batch Rule

Do not reopen:
- ceiling theory
- seasonality theory
- share assumptions
- scoring architecture

Do not add:
- new model features
- new UI design
- new research notes

Only do:
- recommendation-governance fix
- test updates
- rerun and evidence

## Task 1 - Lock Critical Amazon Recommendation Cap

### Goal

Implement the v1 rule for critical Amazon risk so the recommendation output is commercially safer and easier to trust.

### Required implementation

Update:
- `scripts/flows/F/F073_build_backtest_summary.py`

Implement a recommendation-cap rule for:
- `amazon_risk_level = critical`

### Required v1 behavior

For rows with:
- `summary_status = ready`
- `amazon_risk_level = critical`

the recommendation must not remain:
- `Normal fit`
- `Managed fit`

Allowed outputs after cap:
- `Exit-only`
- `Avoid`
- `Manual review` if confidence or readiness forces that state

### Practical expectation

This is a governance cap, not a full model redesign.

Meaning:
- keep existing scores
- keep existing replay output
- only cap the recommendation state when critical Amazon risk is present

### Tests to update

Update:
- `tests/test_f073_build_backtest_summary.py`
- `tests/test_f002_build_backtest_calibration_set.py`

Add test coverage for:
- critical Amazon rows are capped away from `Normal fit` / `Managed fit`
- non-critical rows are not incorrectly capped
- calibration mismatch flag count falls when summary logic is rerun

### Test command

```powershell
pytest tests/test_f073_build_backtest_summary.py tests/test_f002_build_backtest_calibration_set.py
```

### Acceptance criteria

- no `ready` summary row with `amazon_risk_level = critical` returns `Normal fit` or `Managed fit`
- no unrelated recommendation states are changed by accident
- test updates pass

### Proof required

Show:
- changed recommendation rule in summary logic
- post-rerun count of rows where:
  - `amazon_risk_level = critical`
  - and recommendation in `Normal fit`, `Managed fit`

## Task 2 - Rerun Full F Backtest Chain

### Goal

Rebuild the current backtest outputs after the recommendation-cap change.

### Run order

Run:

```powershell
python -m scripts.flows.F.F070_build_backtest_policy_snapshot
python -m scripts.flows.F.F071_build_backtest_input_view
python -m scripts.flows.F.F072_run_backtest_replay
python -m scripts.flows.F.F073_build_backtest_summary
python -m scripts.flows.F.F074_build_backtest_health
python scripts/one_off/F002_build_backtest_calibration_set.py
```

### Acceptance criteria

- all 6 commands complete successfully
- `feeder_backtest_health.csv` remains fully `ok`
- calibration set rebuilds

### Proof required

Show:
- row counts from:
  - `feeder_backtest_policy_live.csv`
  - `feeder_backtest_input_view_live.csv`
  - `feeder_backtest_replay_daily_live.csv`
  - `feeder_backtest_summary_live.csv`
  - `feeder_backtest_health.csv`
  - `f_backtest_calibration_set_latest.csv`

## Task 3 - Full Test Pack

### Goal

Prove the closeout change does not break the current backtest and O integration.

### Exact pack

Run:

```powershell
pytest tests/test_f000_paths_and_schemas.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f002_build_backtest_calibration_set.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py
```

### Acceptance criteria

- full pack passes
- no new schema regressions
- no O integration regressions

### Proof required

Show:
- pytest result summary

## Task 4 - Final Sign-Off Evidence

### Goal

Return one clean evidence block showing whether the backtest phase is now ready for sign-off.

### Required evidence summary

Return:
- changed files
- test results
- final `feeder_backtest_health.csv`
- final calibration mismatch count
- final count of critical-Amazon rows still returning `Normal fit` or `Managed fit`
- final recommendation breakdown counts
- whether v1 backtest is now ready for sign-off

### Expected end-state

This batch is complete when:
- critical Amazon recommendation cap is active
- targeted tests pass
- full test pack passes
- health file remains all `ok`
- calibration mismatch count is reduced to `0`, or any remaining rows are explicitly justified in the reply

## Not In This Batch

Do not do these here unless a clear defect is discovered:
- new scoring features
- threshold redesign
- new competition logic
- new UI sections
- guidebook expansion beyond small factual updates

## Suggested Final Output Back To User

When this batch is done, the Codex response should include:
- what changed
- which files changed
- test results
- final health summary
- final mismatch count
- whether the backtest phase is now ready for sign-off
