# Execution Batch 008

## Purpose
- Align F backtest pass behavior with the user through guided scenario review, then prove that policy changes can rerun historical outputs and still behave correctly in both future scan modes.

## Scope guardrails
- Only do:
  - build a representative review sample from current F backtest and screening outputs
  - walk through sample buckets with the user in plain English
  - record aligned expectations durably in the active plan folder
  - lock the historical refresh path so changed rules can reclassify past outputs truthfully
  - make the operator-facing decision state simple enough to read (`pass`, `fail`, `manual_review`) while keeping richer fit labels underneath
  - validate future F scan behavior in both `screening` and `data_collection`
- Do not change:
  - H runtime logic
  - Google Sheets or local DB state
  - raw evidence files by hand
  - past outputs by manual CSV edits instead of rerun
- Do not add:
  - future-only rule changes that cannot be applied to past evidence
  - per-ASIN patch lists as the main decision engine
  - auto-live-policy writes from backtest

## Files allowed to change
- `plans/active/f-cycle-backtest-v1/EXECUTION_BATCH_008.md`
- `plans/active/f-cycle-backtest-v1/USER_ALIGNMENT_NOTES.md`
- `plans/active/f-cycle-backtest-v1/PLAN.md`
- `plans/active/f-cycle-backtest-v1/PLAN_STATUS.md`
- `scripts/one_off/F002_build_backtest_calibration_set.py`
- `scripts/one_off/F003_refresh_backtest_after_policy_change.py`
- `scripts/flows/F/F061_run_legacy_first_checks_local.py`
- `scripts/flows/F/F073_build_backtest_summary.py`
- `scripts/flows/F/F074_build_backtest_health.py`
- `scripts/flows/F/F075_apply_backtest_policy_updates.py`
- `scripts/flows/F/_schemas.py`
- `scripts/flows/O/O001_build_restock_source_view.py`
- `scripts/flows/O/O400_operator_ui.py`
- `tests/test_f002_build_backtest_calibration_set.py`
- `tests/test_f061_run_legacy_first_checks_local.py`
- `tests/test_f073_build_backtest_summary.py`
- `tests/test_f074_build_backtest_health.py`
- `tests/test_f075_apply_backtest_policy_updates.py`
- `tests/test_o001_restock_source_view.py`
- `tests/test_o_ui_operator_view.py`

## Inputs to read first
- `AGENTS.md`
- `CODEX.md`
- `plans/active/f-cycle-backtest-v1/PLAN.md`
- supporting files:
  - `reference/Backtest Strategy Ideas/F_cycle_backtest_working_notes.md`
  - `reference/Backtest Strategy Ideas/finalisation1.md`
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
  - `scripts/one_off/F002_build_backtest_calibration_set.py`
  - `scripts/one_off/F003_refresh_backtest_after_policy_change.py`
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - `out/systems/F/live/f_screening_row_state_live.csv`
  - `out/analysis_reports/f_backtest_calibration_set_latest.csv`
  - `out/analysis_reports/f_backtest_calibration_set_latest.md`

## Tasks
### Task 1
- Goal:
  - turn the current backtest outputs into a human-reviewable scenario pack rather than a technical dump
- Files:
  - `scripts/one_off/F002_build_backtest_calibration_set.py`
  - `tests/test_f002_build_backtest_calibration_set.py`
- Notes:
  - reuse the existing calibration artifact rather than inventing a second review subsystem
  - add scenario bucket coverage for:
    - `certain_fail`
    - `almost_pass`
    - `just_passed`
    - `on_the_line`
    - `manual_review_or_unclear`
    - `demand_or_profit_inflation_risk`
    - Amazon-risk and compression-risk cases where confidence is high enough to learn from
  - include a short plain-English review prompt per row so the user can react without reading raw metrics first
  - do not review every ASIN; review enough rows in each bucket to understand the pattern

### Task 2
- Goal:
  - run guided sample checks with the user and store the agreed expectation patterns durably
- Files:
  - `plans/active/f-cycle-backtest-v1/USER_ALIGNMENT_NOTES.md`
- Notes:
  - each reviewed row must end in one simple agreed label:
    - `rightful_fail`
    - `rightful_pass`
    - `too_harsh`
    - `too_soft`
    - `unclear_due_to_data`
  - capture the plain-English reason, not a developer debate transcript
  - stop opening more ASINs once a pattern is repeating clearly
  - the end state of this task is coordinated expectations between the user and the backtest behavior

### Task 3
- Goal:
  - make policy changes rerun historical outputs truthfully and expose a simple decision state
- Files:
  - `scripts/one_off/F003_refresh_backtest_after_policy_change.py`
  - `scripts/flows/F/F073_build_backtest_summary.py`
  - `scripts/flows/F/F074_build_backtest_health.py`
  - `scripts/flows/F/F075_apply_backtest_policy_updates.py`
  - `scripts/flows/F/_schemas.py`
  - `scripts/flows/O/O001_build_restock_source_view.py`
  - `scripts/flows/O/O400_operator_ui.py`
  - related tests in `tests/`
- Notes:
  - changed rules must be able to flip old results by rerunning the same raw history under the new policy
  - no hand-editing of existing `Avoid` / `Exit-only` / `Normal fit` rows
  - summary should expose a simple operator-facing decision state such as `pass`, `fail`, or `manual_review`
  - the richer fit labels can stay, but they should sit beneath the simpler decision layer
  - health must call out stale or mixed-policy output states if refresh is incomplete

### Task 4
- Goal:
  - prove future F scans behave correctly in both `screening` and `data_collection` modes
- Files:
  - `scripts/flows/F/F061_run_legacy_first_checks_local.py`
  - `tests/test_f061_run_legacy_first_checks_local.py`
- Notes:
  - `screening` mode must be the normal decision-producing path
  - `data_collection` mode must collect evidence without pretending it has a final pass/fail decision when it does not
  - this proof must make the boundary clear so future scans do not confuse evidence collection with final commercial judgment

### Task 5
- Goal:
  - rerun the proof chain after any code changes so the new behavior is evidenced, not implied
- Files:
  - backtest refresh chain outputs under `out/systems/F/live/`
  - calibration outputs under `out/analysis_reports/`
- Notes:
  - if Batch 008 changes code, rerun the relevant refresh chain and capture row-count and decision-state proof
  - if Batch 008 only changes plan files, do not claim runtime success

## Tests
- Command:

```powershell
pytest tests/test_f002_build_backtest_calibration_set.py tests/test_f061_run_legacy_first_checks_local.py tests/test_f070_build_backtest_policy_snapshot.py tests/test_f071_build_backtest_input_view.py tests/test_f072_run_backtest_replay.py tests/test_f073_build_backtest_summary.py tests/test_f074_build_backtest_health.py tests/test_f075_apply_backtest_policy_updates.py tests/test_o001_restock_source_view.py tests/test_o_ui_operator_view.py
```

- Expected result:
  - full pack passes

## Proof required
- Row counts:
  - updated calibration artifact reports bucket counts for the new scenario pack
  - refreshed summary output reports simple decision-state counts as well as richer recommendation counts
- Health rows:
  - backtest health remains truthful after refresh
  - any new decision-state or historical-refresh health check is present and current
- Output files:
  - `out/analysis_reports/f_backtest_calibration_set_latest.csv`
  - `out/analysis_reports/f_backtest_calibration_set_latest.md`
  - `plans/active/f-cycle-backtest-v1/USER_ALIGNMENT_NOTES.md`
  - `out/systems/F/live/feeder_backtest_summary_live.csv`
  - any touched O surfaces or source-view outputs if decision state is surfaced there
- Notes:
  - prove at least one controlled fixture where a policy change rerun can move a historical row across the decision boundary
  - prove `screening` and `data_collection` separately
  - keep the explanation plain-English and root-cause first

## Completion checklist
- [ ] Scope held
- [ ] Files changed only in allowed set
- [ ] User sample review method written down
- [ ] Historical refresh path defined as the official policy-change rerun path
- [ ] Simple decision state locked without hiding richer fit labels
- [ ] Dual-mode behavior defined and tested
- [ ] Tests passed
- [ ] Proof captured
