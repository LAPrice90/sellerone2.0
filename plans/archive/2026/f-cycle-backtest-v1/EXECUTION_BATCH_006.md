# F Cycle Backtest - Execution Batch 6

## Purpose

Add attribution-confidence enrichment to backtest input and summary flow.

## Batch Goal

Make confidence and reasoning more truthful when identity or demand attribution is weak.

## Important Batch Rule

Do not change:
- replay math
- policy controls
- UI controls

Only change:
- confidence/reason-tag logic in F071 and F073
- scoped health visibility in F074
- tests and proof artifacts

## Task 1 - Attribution Confidence Enrichment In F071

### Goal

Generate attribution reason tags and fold attribution confidence into history confidence.

### Required implementation

Update:
- `scripts/flows/F/F071_build_backtest_input_view.py`

### Required behavior

- derive attribution-confidence level using mapping quality, coverage, and channel pairing
- downgrade final `history_confidence` when attribution confidence is weaker
- emit attribution reason tags into `input_reason_codes`
- force manual review only when attribution confidence is low

## Task 2 - Carry Attribution Tags Into Summary

### Goal

Expose attribution caveats in summary reason codes for ready rows.

### Required implementation

Update:
- `scripts/flows/F/F073_build_backtest_summary.py`

### Required behavior

- carry attribution reason tags from input into `summary_reason_codes` for ready rows
- update `share_assumption_basis` to the measured-share label

## Task 3 - Attribution Health Check

### Goal

Add scoped health coverage for attribution-risk concentration.

### Required implementation

Update:
- `scripts/flows/F/F074_build_backtest_health.py`

### Required check

`f_backtest_attribution_confidence_share`:
- tracks share of ready rows with severe attribution tags
- warn when severe share is high
- ok when severe share is within tolerance

## Task 4 - Test Pack And Proof Rerun

### Test command

```powershell
pytest tests/test_f071_build_backtest_input_view.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py
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

- attribution caveats are visible in input and summary outputs
- confidence downgrades are explicit and test-covered
- attribution health check is present and passing
- refreshed outputs and calibration pack are current
