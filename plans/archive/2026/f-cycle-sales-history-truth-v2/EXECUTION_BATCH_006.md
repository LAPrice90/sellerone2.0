# Execution Batch 006

## Purpose
- Build the validation and accuracy pack that compares model outputs against sampled operator checks.
- Expose mismatch/error buckets explicitly so weak spots are visible, not hidden.

## Why this batch exists
- Batch 005 made decision confidence explicit and health-checked.
- We still need operator-grounded accuracy evidence for sampled ASINs.
- The missing contract is a repeatable one-off accuracy export that joins:
  - sampled calibration rows
  - latest summary decision outputs
  - operator check inputs (including Amazon sold-in-last-30-days checks)

## Scope guardrails
- Only do:
  - add one-off accuracy script(s) under `scripts/one_off`
  - add tests for parsing, join logic, and mismatch bucketing
  - update active plan docs for Batch 006 proof
- Do not change:
  - Google Sheets
  - local DB state
  - daily loops
  - scrape runtime path
  - F070 to F074 decision engine logic
- Do not add:
  - downstream masking of mismatches
  - implicit pass/fail overrides without explicit bucket reasons

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_006.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
- `scripts/one_off/F011_build_sales_history_accuracy_pack.py`
- related tests under `tests/`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `project_control/OPERATING_SYSTEM.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
- `out/analysis_reports/f_backtest_calibration_set_latest.csv`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/analysis_reports/f_sales_history_validation_latest.csv`

## Batch 005 gate facts to carry forward
- `F073` rows: `2358` (`decision_fail=1883`, `decision_pass=266`, `manual_review=209`)
- `F074` rows: `21` (`ok=21`, `warn=0`, `fail=0`)
- decision confidence integrity:
  - `f_backtest_decision_confidence_integrity = ok`
- sampled validation export:
  - rows `28668`
  - decision confidence columns present

## Tasks

### Task 1
- Goal:
  - define operator-check input contract for sampled ASIN accuracy comparison
- Notes:
  - keep input one-off and file-based
  - support sold-in-last-30-days text formats (`10`, `~10`, `<10`)

### Task 2
- Goal:
  - build one-off accuracy pack by joining calibration rows with summary and operator checks
- Notes:
  - output row-level model vs operator comparison
  - output explicit mismatch/error buckets
  - keep unresolved checks visible as missing-data buckets

### Task 3
- Goal:
  - emit summary counts for operator sign-off
- Notes:
  - include:
    - rows evaluated
    - rows with operator units
    - decision-aligned/mismatch counts
    - bucket distribution

### Task 4
- Goal:
  - add tests for parse/join/bucket logic and run scoped proof
- Notes:
  - no ad-hoc manual data edits
  - one-off script run must produce latest artifacts

## Tests
- Minimum command:

```powershell
pytest tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f002_build_backtest_calibration_set.py
```

- Plus:
  - `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py tests/test_f011_build_sales_history_accuracy_pack.py`

## Proof required
- Accuracy-pack output proof:
  - row-level CSV exists with bucketed outcomes
  - latest pointer file exists
  - summary CSV exists with bucket totals
- Logic proof:
  - tests cover:
    - sold-30d parsing edge cases
    - no-operator-check bucketing
    - decision mismatch bucketing
    - confidence-overstated bucketing on severe mismatch
- Runtime proof:
  - one-off script runs successfully on current repo data
  - output row counts and bucket counts reported

## Completion checklist
- [x] Operator-check contract added in one-off script
- [x] Accuracy pack builder implemented
- [x] Accuracy summary output implemented
- [x] Tests added and passing
- [x] One-off runtime proof captured

## Execution evidence
- Isolated verification:
  - `pytest -q tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f002_build_backtest_calibration_set.py`
  - result: `10 passed`
  - `python -m py_compile scripts/one_off/F011_build_sales_history_accuracy_pack.py tests/test_f011_build_sales_history_accuracy_pack.py`
  - result: pass
- Runtime proof:
  - `python scripts/one_off/F011_build_sales_history_accuracy_pack.py --observed-utc 2026-04-20T12:53:00Z`
  - result:
    - status: `success`
    - rows_total: `18`
    - mismatch_rows: `0`
    - needs_operator_input_rows: `18`
    - output files written:
      - `out/analysis_reports/f_sales_history_accuracy_pack_latest.csv`
      - `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`
      - `out/analysis_reports/f_operator_sales_checks_template_latest.csv`
- Summary proof from latest output:
  - `rows_with_operator_check=0`
  - `rows_with_operator_units=0`
  - `rows_with_operator_decision=0`
  - `bucket::missing_operator_check=18`
  - `bucket::missing_operator_units=18`
  - `bucket::missing_operator_decision=18`
