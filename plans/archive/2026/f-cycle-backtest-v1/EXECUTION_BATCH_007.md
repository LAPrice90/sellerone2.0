# F Cycle Backtest - Execution Batch 7

## Purpose

Tighten measured-share governance so replay outputs stay realistic under shared-competition scenarios and sparse evidence.

## Batch Goal

Improve trust in replay sales-share values by:
- applying scenario caps to measured shared-market rates
- exposing when replay rows rely on global-prior fallback
- adding a scoped health check for prior-reliance concentration

## Important Batch Rule

Do not change:
- ROI ladder and replay mode transitions
- O flow integration
- policy control surface

Only change:
- measured-share governance in `F072`
- summary share-assumption labeling and reason tags in `F073`
- health visibility in `F074`
- scoped tests and proof artifacts

## Task 1 - Scenario Share Governance In Replay

### Goal

Prevent unrealistic high share assumptions in shared scenarios.

### Required implementation

Update:
- `scripts/flows/F/F072_run_backtest_replay.py`

### Required behavior

- apply explicit scenario caps to measured shared-market share values
- tag rows when caps are applied
- tag rows when scenario share is sourced from global prior

## Task 2 - Summary Basis And Share Governance Tags

### Goal

Make summary output explicit about the governed-share model in use.

### Required implementation

Update:
- `scripts/flows/F/F073_build_backtest_summary.py`

### Required behavior

- update `share_assumption_basis` label to the governed-share basis
- carry replay share-governance tags into ready summary reason codes

## Task 3 - Prior Dependency Health Check

### Goal

Detect when replay is over-dependent on global-prior share assumptions.

### Required implementation

Update:
- `scripts/flows/F/F074_build_backtest_health.py`
- `tests/test_f074_build_backtest_health.py`

### Required check

`f_backtest_share_prior_dependency`:
- fail when replay schema is invalid
- warn when prior-dependent replay rows exceed threshold
- ok otherwise

## Task 4 - Scoped Tests And Proof Rerun

### Test command

```powershell
pytest tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py
```

### Rerun order

```powershell
python -m scripts.flows.F.F071_build_backtest_input_view
python -m scripts.flows.F.F072_run_backtest_replay
python -m scripts.flows.F.F073_build_backtest_summary
python -m scripts.flows.F.F074_build_backtest_health
python scripts/one_off/F002_build_backtest_calibration_set.py
```

## Expected End State

- replay sales-share assumptions are governed and tagged
- summary clearly states governed measured-share basis
- health includes prior-dependency visibility
- scoped tests pass and refreshed artifacts are current
