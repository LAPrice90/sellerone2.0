# Project Brief

## Ticket
- Ticket name: F cycle backtest v1
- Date opened: 2026-04-11
- Owner: Codex active-plan switch based on existing 2026-04-10 source plan and execution batches

## Business problem
- The backtest itself is already built, but the durable tracking still lived in `reference/Backtest Strategy Ideas/`.
- New sessions now expect the current ticket to live under `plans/active/<plan_slug>/`, so future work risked drifting away from the real completed state.

## Goal
- Put the backtest into the new active planning system without changing the backtest math.
- Preserve the existing coding plan, execution batches, and proof trail in one active plan folder.
- Write a plain-language current-state snapshot so the next batch starts from facts, not memory.

## Why now
- The repo now has an explicit planning flow in `plans/` and `CODEX.md`.
- The backtest is far enough along that the main risk is tracking drift, not missing architecture.
- The next continuation batch should start from the real end-state of Batches 001 to 003.

## Constraints
- Existing system boundaries:
  - F owns the historical backtest outputs.
  - O owns the operator UI surface.
  - H runtime must not be changed by this ticket.
- Out of scope:
  - replay math changes
  - threshold redesign
  - scheduler or live-loop integration
  - Google Sheets or local DB changes
- Approval-sensitive areas:
  - no work-log append in this ticket unless the user explicitly approves logging this switch-over

## Definition of success
- Observable result 1: `plans/active/f-cycle-backtest-v1/` exists with the real source plan and execution batches copied in.
- Observable result 2: `PROJECT_BRIEF.md`, `PLAN.md`, `PLAN_STATUS.md`, `DATA_CONTRACTS.md`, and `RUNBOOK.md` state the actual current backtest status.
- Observable result 3: the next continuation point is written down clearly enough for a fresh session to resume without rereading the whole reference folder.

## Reference material
- Research notes:
  - `reference/Backtest Strategy Ideas/F_cycle_backtest_working_notes.md`
  - `reference/Backtest Strategy Ideas/finalisation1.md`
- Related repo files:
  - `scripts/flows/F/F070_build_backtest_policy_snapshot.py`
  - `scripts/flows/F/F071_build_backtest_input_view.py`
  - `scripts/flows/F/F072_run_backtest_replay.py`
  - `scripts/flows/F/F073_build_backtest_summary.py`
  - `scripts/flows/F/F074_build_backtest_health.py`
  - `scripts/flows/F/F075_apply_backtest_policy_updates.py`
  - `scripts/flows/O/O400_operator_ui.py`
  - `project_control/F_BACKTEST_V1_GUIDEBOOK.md`
- Prior tickets or plans:
  - `reference/Backtest Strategy Ideas/F_cycle_backtest_coding_plan_v1.md`
  - `reference/Backtest Strategy Ideas/F_cycle_backtest_execution_batch_1.md`
  - `reference/Backtest Strategy Ideas/F_cycle_backtest_execution_batch_2.md`
  - `reference/Backtest Strategy Ideas/F_cycle_backtest_execution_batch_3.md`
