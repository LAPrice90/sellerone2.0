# Execution Batch 001

## Purpose
- Lock demand truth into the current F pipeline by separating raw completed-month demand from price-qualified monthly demand, then rebuild a validation pack the user can check against live Amazon/BBP evidence.

## Scope guardrails
- Only do:
  - lock the first sales-history business contract inside the existing F outputs
  - add price-qualified monthly demand and monthly profit fields
  - add history maturity fields
  - expose explicit reason codes when raw demand is discounted or excluded
  - refresh health so stale or mismatched states are visible truthfully
  - build a one-off validation audit from sampled ASINs
- Do not change:
  - H runtime
  - Google Sheets
  - local DB state
  - post-purchase learning loop yet
  - live operator surfaces beyond what the current F summary already owns
- Do not add:
  - manual per-ASIN override lists as core logic
  - current-month or predicted-month demand as the trusted demand basis
  - one-off validation scripts inside daily loops

## Files allowed to change
- `plans/archive/2026/f-cycle-sales-history-truth-v2/EXECUTION_BATCH_001.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN_STATUS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/RUNBOOK.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/DECISION_MODEL.md`
- `scripts/flows/F/legacy_scanner_2_1/Webscrape.py`
- `scripts/flows/F/F070_build_backtest_policy_snapshot.py`
- `scripts/flows/F/F071_build_backtest_input_view.py`
- `scripts/flows/F/F072_run_backtest_replay.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/F/_source_contracts.py`
- `scripts/one_off/F004_build_bbp_sales_sample_audit.py`
- `scripts/one_off/F005_build_sales_history_validation_audit.py`
- `tests/test_f004_build_bbp_sales_sample_audit.py`
- `tests/test_f005_build_sales_history_validation_audit.py`
- `tests/test_f070_build_backtest_policy_snapshot.py`
- `tests/test_f071_build_backtest_input_view.py`
- `tests/test_f072_run_backtest_replay.py`
- `tests/test_f073_build_backtest_summary.py`
- `tests/test_f074_build_backtest_health.py`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `project_control/OPERATING_SYSTEM.md`
- `plans/archive/2026/f-cycle-sales-history-truth-v2/PLAN.md`
- supporting files:
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/DATA_CONTRACTS.md`
  - `plans/archive/2026/f-cycle-sales-history-truth-v2/DECISION_MODEL.md`
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
  - `plans/archive/2026/f-cycle-backtest-v1/EXECUTION_BATCH_008.md`
  - `plans/archive/2026/f-cycle-backtest-v1/EXECUTION_BATCH_009.md`
  - `plans/archive/2026/f-cycle-backtest-v1/USER_ALIGNMENT_NOTES.md`
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`

## Tasks
### Task 1
- Goal:
  - add the first price-qualified demand fields into the existing F input view
- Files:
  - `scripts/flows/F/F071_build_backtest_input_view.py`
  - `scripts/flows/F/_schemas.py`
  - `scripts/flows/F/_source_contracts.py`
  - tests above
- Notes:
  - use trusted completed-month raw units as the starting point
  - calculate a first monthly qualified-units estimate based on:
    - days above our floor
    - share assumptions already owned by replay
    - explicit zeroing/discounting when Amazon or market price sits below our floor
  - add `history_maturity_state`
  - do not pretend this is seasonality yet

### Task 2
- Goal:
  - carry the qualified-demand fields into the summary and make the commercial rule visible
- Files:
  - `scripts/flows/F/F072_run_backtest_replay.py`
  - `scripts/flows/F/F073_build_backtest_summary.py`
  - tests above
- Notes:
  - summary must show:
    - raw monthly units
    - qualified monthly units
    - qualified monthly profit
  - below `GBP 20` expected monthly profit should normally fail unless another explicit rule later says otherwise
  - keep richer fit labels if needed, but make the commercial outcome easy to read

### Task 3
- Goal:
  - refresh health truth and add checks for price-qualified demand
- Files:
  - `scripts/flows/F/F074_build_backtest_health.py`
  - tests above
- Notes:
  - stale health must be visible
  - add checks that fail or warn when:
    - raw demand is being used where qualified demand should drive the decision
    - maturity state is missing
    - current live files are newer than health
  - explain the current input-view row-count mismatch or flag it clearly if still unresolved

### Task 4
- Goal:
  - build a one-off validation audit for sampled ASINs
- Files:
  - `scripts/one_off/F004_build_bbp_sales_sample_audit.py`
  - `scripts/one_off/F005_build_sales_history_validation_audit.py`
  - tests above
- Notes:
  - the audit must let the user compare:
    - raw completed-month units
    - qualified monthly units
    - qualified monthly profit
    - mismatch reason
  - keep this one-off only

## Tests
- Command:

```powershell
pytest tests/test_f004_build_bbp_sales_sample_audit.py tests/test_f005_build_sales_history_validation_audit.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py
```

- Expected result:
  - scoped sales-history truth pack passes

## Proof required
- Row counts:
  - updated input-view row count
  - updated summary row count
  - counts by `history_maturity_state`
  - counts by decision state once exposed
- Health rows:
  - refreshed `feeder_backtest_health.csv` is at least as new as input/replay/summary
  - `f_backtest_demand_basis_integrity` remains truthful
  - new price-qualified-demand and stale-health checks are present
- Output files:
  - `out/systems/F/live/feeder_backtest_input_view_live.csv`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/feeder_backtest_health.csv`
  - `out/analysis_reports/f_backtest_bbp_sales_sample_audit_latest.csv`
  - `out/analysis_reports/f_sales_history_validation_latest.csv`
- Notes:
  - prove at least one sampled ASIN where raw monthly units are higher than qualified monthly units because the market sat below our floor
  - keep the explanation plain-English and root-cause first

## Completion checklist
- [x] Scope held
- [x] Files changed only in allowed set
- [x] Raw versus qualified demand is explicit
- [x] `GBP 20` monthly profit floor is surfaced truthfully
- [x] Health rebuilt and current
- [x] Validation audit built
- [x] Tests passed
- [x] Proof captured
- [x] Reply file updated
