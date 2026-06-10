# Execution Batch 005

## Purpose
- Implement the business decision summary and confidence engine on top of the Batch 004 classifier contract.
- Keep decision outputs explicit and auditable: `pass`/`fail`/`manual_review`, expected monthly units/profit now, confidence, and reason tags.

## Why this batch exists
- Batch 004 closed classifier integrity:
  - `f_backtest_seasonality_classifier_integrity = ok`
  - `f_backtest_stability_classifier_integrity = ok`
  - `f_backtest_recent_vs_baseline_integrity = ok`
- Current summary already emits decision state and floor handling, but confidence is still implicit.
- Batch 005 makes confidence explicit in summary, health, and validation outputs so operator review is not guesswork.

## Scope guardrails
- Only do:
  - implement decision confidence outputs in F-owned summary path
  - keep decision state root-caused from summary confidence and profit floor logic
  - add F-scoped health integrity for confidence contract
  - expose confidence fields in one-off validation audit export
  - add or extend scoped tests
- Do not change:
  - Google Sheets
  - local DB state
  - scrape runtime owner path
  - post-purchase learning loop
  - H runtime
- Do not add:
  - downstream masking to hide low-confidence decisions
  - manual CSV truth patches
  - ad-hoc broad scrape runs as a substitute for decision-contract proof

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_005.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- related tests under `tests/`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `project_control/OPERATING_SYSTEM.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DECISION_MODEL.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_004.md`
- `out/systems/F/live/feeder_backtest_input_view_live.csv`
- `out/systems/F/live/feeder_backtest_replay_daily_live.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/systems/F/live/feeder_backtest_health.csv`
- `out/analysis_reports/f_sales_history_validation_latest.csv`

## Batch 004 gate facts to carry forward
- `F071`: rows `2358` (`ready=2149`, `manual_review=209`)
- `F072`: rows `769366`
- `F073`: rows `2358` (`ready=2149`, `manual_review=209`)
- `F074`: rows `20` (`ok=20`, `warn=0`, `fail=0`)
- `F005`: rows `28668`, trusted rows `2262`, qualified-delta rows `28418`
- READY classifier completeness:
  - blank classifier states: `0`
  - blank classifier reason path: `0`

## Tasks

### Task 1
- Goal:
  - add explicit decision confidence engine in summary owner
- Notes:
  - output confidence as `high`/`medium`/`low`
  - output explicit confidence reason codes
  - confidence must remain root-caused from summary readiness, maturity, qualified source truth, and classifier context

### Task 2
- Goal:
  - integrate confidence with decision-state output
- Notes:
  - keep `expected_profit_below_floor -> fail`
  - route low-confidence ready rows to `manual_review`
  - include confidence tags in decision reason path

### Task 3
- Goal:
  - extend F health to enforce confidence contract
- Notes:
  - add `f_backtest_decision_confidence_integrity`
  - fail on invalid or blank confidence fields on READY rows
  - fail if READY `pass` rows carry `low` confidence

### Task 4
- Goal:
  - expose decision confidence in one-off validation export
- Notes:
  - add confidence fields to `f_sales_history_validation_latest.csv`
  - keep one-off boundary intact (no daily-loop import)

### Task 5
- Goal:
  - run scoped verification and controlled proof rebuild
- Notes:
  - scoped pytest pack and `py_compile` for changed files
  - rebuild `F071` -> `F074` plus `F005`
  - capture row counts and health statuses after rebuild

## Tests
- Minimum command:

```powershell
pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py
```

- Plus:
  - `python -m py_compile` for each changed F file and changed test file
  - confidence-specific summary and health tests must pass

## Proof required
- Decision output proof:
  - summary rows emit:
    - `decision_state`
    - `decision_confidence`
    - `decision_confidence_reason_codes`
    - expected units/profit now and source fields
  - low-confidence ready rows do not silently emit `pass`
- Health proof:
  - `f_backtest_decision_confidence_integrity = ok`
  - `f_backtest_decision_floor_integrity` remains truthful
  - existing classifier integrity checks remain `ok`
- Validation proof:
  - `f_sales_history_validation_latest.csv` includes decision confidence fields for sampled review
- Controlled rebuild proof:
  - refreshed `F071` to `F074` and `F005` row counts captured after code change

## Completion checklist
- [x] Confidence engine implemented in `F073`
- [x] Decision-state integration updated in `F073`
- [x] Confidence contract added to summary schema
- [x] `F074` confidence integrity check added
- [x] `F005` validation export extended with confidence fields
- [x] Scoped pytest and `py_compile` pass
- [x] Controlled Batch 005 rebuild proof captured

## Execution evidence
- Isolated verification:
  - `pytest tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f005_build_sales_history_validation_audit.py`
  - result: `49 passed`
  - `python -m py_compile` passed for all changed F and test files
- Controlled proof boundary:
  - `F070` (`2026-04-20T15:20:00Z`): rows `1` (`active_rows=1`)
  - `F071` (`2026-04-20T15:21:00Z`): rows `2358` (`ready=2149`, `manual_review=209`)
  - `F072` (`2026-04-20T15:22:00Z`): rows `769366`
  - `F073` (`2026-04-20T15:23:00Z`): rows `2358` (`ready=2149`, `manual_review=209`)
  - `F074` first pass (`2026-04-20T15:24:00Z`): rows `21` (`ok=20`, `warn=1`)
  - `F074` closeout (`2026-04-20T15:25:00Z`): rows `21` (`ok=21`, `warn=0`, `fail=0`)
  - `F005` (`2026-04-20T15:26:00Z`): rows `28668`, trusted rows `2262`, qualified-delta rows `28418`
- Confidence contract proof:
  - READY summary rows: `2149`
  - READY rows with blank `decision_confidence`: `0`
  - READY rows with blank `decision_confidence_reason_codes`: `0`
  - READY `pass` rows with `decision_confidence=low`: `0`
  - summary confidence distribution:
    - `medium=1251`
    - `low=1107`
- Health proof:
  - `f_backtest_health_staleness = ok`
  - `f_backtest_decision_floor_integrity = ok`
  - `f_backtest_decision_confidence_integrity = ok`
  - classifier integrity checks remain `ok`
- Validation proof:
  - `f_sales_history_validation_latest.csv` includes:
    - `decision_confidence`
    - `decision_confidence_reason_codes`
  - rows with populated confidence fields: `28541`
