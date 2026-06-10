# Execution Batch 007

## Purpose
- Implement the post-purchase 90-day learning loop as a one-off evidence workflow.
- Preserve buy-time assumptions, compare them against actual outcomes, and classify why forecasts were right or wrong.

## Why this batch exists
- Batch 005 made decision state and confidence explicit.
- Batch 006 added model-vs-operator accuracy outputs and templates.
- We still do not capture post-purchase truth in a structured F-owned dataset.
- Batch 007 closes that gap so calibration can be based on real outcomes, not only pre-buy estimates.

## Scope guardrails
- Only do:
  - add a one-off learning-pack builder under `scripts/one_off`
  - produce append-safe learning log output
  - produce one-off review and health outputs for operator sign-off
  - add tests for parse, dedupe, classification, and schema integrity
  - update active plan docs with Batch 007 proof
- Do not change:
  - Google Sheets
  - local DB state
  - daily loops
  - scraper runtime path
  - F070 to F074 decision engine logic
- Do not add:
  - hidden backfills that rewrite old assumptions
  - downstream masking of bad outcomes
  - automatic loop promotion without explicit later approval

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_007.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
- `scripts/one_off/F012_build_sales_history_learning_pack.py`
- related tests under `tests/`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `project_control/OPERATING_SYSTEM.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/CODING_PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DECISION_MODEL.md`
- `out/systems/F/live/feeder_backtest_summary_live.csv`
- `out/analysis_reports/f_sales_history_accuracy_pack_latest.csv`
- `out/analysis_reports/f_sales_history_accuracy_summary_latest.csv`

## Batch 006 gate facts to carry forward
- One-off accuracy pack is complete and repeatable:
  - rows: `18`
  - mismatch rows: `0`
  - needs-operator-input rows: `18`
- Operator check template is available but unfilled:
  - `f_operator_sales_checks_template_latest.csv`: rows `18`
- Decision confidence contract is active from Batch 005:
  - `f_backtest_decision_confidence_integrity = ok`

## Tasks

### Task 1
- Goal:
  - define learning input contracts for buy-time assumptions and observed outcomes
- Notes:
  - assumptions should come from trusted F decision outputs
  - outcomes should support 30d, 60d, and 90d checkpoints
  - contract stays one-off and file-based

### Task 2
- Goal:
  - build append-safe learning log output
- Notes:
  - output path:
    - `out/systems/F/live/feeder_sales_history_learning_live.csv`
  - dedupe key must prevent duplicate decision snapshots
  - preserve original buy-time assumptions without rewriting history

### Task 3
- Goal:
  - emit one-off learning review pack and health summary
- Notes:
  - outputs:
    - `out/analysis_reports/f_sales_history_learning_review_latest.csv`
    - `out/analysis_reports/f_sales_history_learning_health_latest.csv`
    - `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv`
  - classification outcomes must be explicit and reason-coded

### Task 4
- Goal:
  - add scoped tests for learning-pack logic
- Notes:
  - cover:
    - missing-input handling
    - dedupe behavior
    - outcome classification
    - schema columns
  - no manual edits to make tests pass

### Task 5
- Goal:
  - run one-off proof and report counts for sign-off
- Notes:
  - run script on current repo data
  - report row counts and missing-outcome counts
  - keep unresolved outcomes visible, not suppressed

## Tests
- Minimum command:

```powershell
pytest tests/test_f012_build_sales_history_learning_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py
```

- Plus:
  - `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py tests/test_f012_build_sales_history_learning_pack.py`

## Proof required
- Learning-log output proof:
  - `feeder_sales_history_learning_live.csv` exists
  - latest pointer output files exist for review, health, and template
  - dedupe key integrity is enforced
- Logic proof:
  - tests cover:
    - missing outcomes
    - duplicate snapshot prevention
    - controlled `learning_outcome` value set
    - reason-code population
- Runtime proof:
  - one-off script runs successfully on current repo data
  - row counts and outcome distribution are reported

## Completion checklist
- [x] Learning input contract added in one-off script
- [x] Learning log builder implemented
- [x] Learning review and health outputs implemented
- [x] Tests added and passing
- [x] One-off runtime proof captured

## Execution evidence
- Isolated verification:
  - `pytest -q tests/test_f012_build_sales_history_learning_pack.py tests/test_f011_build_sales_history_accuracy_pack.py tests/test_f005_build_sales_history_validation_audit.py`
  - result: `8 passed`
  - `python -m py_compile scripts/one_off/F012_build_sales_history_learning_pack.py tests/test_f012_build_sales_history_learning_pack.py`
  - result: pass
- Runtime proof:
  - `python scripts/one_off/F012_build_sales_history_learning_pack.py --observed-utc 2026-04-20T13:02:00Z`
  - result:
    - status: `success`
    - rows_total: `266`
    - rows_pending_outcome: `266`
    - output files written:
      - `out/systems/F/live/feeder_sales_history_learning_live.csv`
      - `out/analysis_reports/f_sales_history_learning_review_latest.csv`
      - `out/analysis_reports/f_sales_history_learning_health_latest.csv`
      - `out/analysis_reports/f_sales_history_learning_actuals_template_latest.csv`
- Health proof from latest output:
  - `rows_total=266`
  - `rows_with_actuals_30d=0`
  - `rows_with_actuals_60d=0`
  - `rows_with_actuals_90d=0`
  - `rows_with_outcome=0`
  - `rows_pending_outcome=266`
  - `outcome::pending_outcome=266`
