# F Cycle Backtest - Execution Batch 5

## Purpose

Replace the provisional shared-sales assumption with measured scenario rates in replay.

## Batch Goal

Move replay share logic from:
- fixed scenario defaults (`100` solo and `50` shared)

to:
- measured per-ASIN scenario rates with global-prior fallback for sparse history

## Important Batch Rule

Do not change:
- ROI ladder rules
- replay status model
- summary scoring model
- UI policy controls

Only change:
- scenario share estimation path in F072
- related tests
- scoped health check coverage for sales-share validity

## Task 1 - Measured Share Estimation In Replay

### Goal

Use observed scenario evidence to estimate share instead of fixed placeholder rates.

### Required implementation

Update:
- `scripts/flows/F/F072_run_backtest_replay.py`

### Required behavior

- derive scenario per day using existing scenario keys
- compute measured share signal from observed chart history
- blend ASIN-level scenario rate with global scenario prior for sparse ASIN history
- keep safe fallback when measured history is unavailable

## Task 2 - Replay Tests For Measured Share

### Goal

Prove measured-share behavior and sparse-history fallback.

### Required implementation

Update:
- `tests/test_f072_run_backtest_replay.py`

### Required assertions

- Amazon-owned Buy Box scenario can drive share to `0`
- sparse scenario samples use prior blending and do not jump straight to `100`
- existing replay path still writes rows and preserves base behavior

## Task 3 - Sales-Share Health Check

### Goal

Add one scoped health check item for the new share model.

### Required implementation

Update:
- `scripts/flows/F/F074_build_backtest_health.py`
- `tests/test_f074_build_backtest_health.py`

### Required check

`f_backtest_sales_share_validity`:
- fail for invalid or out-of-bounds share values
- warn for missing share values
- warn for suspiciously high Amazon-scenario shares
- ok otherwise

## Task 4 - Proof Rerun Chain

### Goal

Regenerate the affected outputs and confirm all checks are healthy.

### Run order

```powershell
python -m scripts.flows.F.F071_build_backtest_input_view
python -m scripts.flows.F.F072_run_backtest_replay
python -m scripts.flows.F.F073_build_backtest_summary
python -m scripts.flows.F.F074_build_backtest_health
python scripts/one_off/F002_build_backtest_calibration_set.py
```

## Expected End State

- replay shares are no longer fixed placeholder values
- health includes scoped share validity check
- test pack passes
- regenerated outputs and calibration pack are current
