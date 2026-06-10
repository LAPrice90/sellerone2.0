# Project Brief

## Ticket
- Ticket name: H repricer strategy alignment and ladder-safe completion
- Date opened: 2026-04-15
- Owner: Codex

## Business problem
- H is now stable enough to inspect strategy, but the live repricer is still hard to judge against the plan.
- We do not yet have a clean answer for when H is selling normally, when it is protecting floor, when it is trying to reset price, and when it is effectively giving up margin.
- Current live logic appears to react mainly to the single best rival, which creates race-to-the-bottom risk when there are multiple live sellers.

## Goal
- Produce a decision-grade next implementation plan that aligns live H behavior with the intended repricer strategy.
- Add ladder-aware strategy rules so H can distinguish:
- one rival worth resetting
- a multi-seller ladder where blind undercutting is irrational
- genuine sell-off conditions
- suppression recovery conditions
- Define outputs that let us measure whether the strategy is working instead of guessing from scattered logs.

## Why now
- Stability is no longer the main blocker.
- The current strategy can now become the main source of lost margin or stuck inventory.
- The next phase should improve decision quality before broader repricer feature expansion.

## Constraints
- Existing system boundaries: no Google Sheets changes, no local DB truth changes, no ad hoc A-cycle runs by Codex, no overlap with H runtime ownership rules.
- Out of scope: portfolio governor, notification-led expansion, demand-learning model, broad pressure workflow.
- Approval-sensitive areas: any live repricer code change, any new write behavior, any change that affects runtime outputs used by health or operator review.

## Definition of success
- Observable result 1: a plain-English alignment report exists with evidence from current H outputs.
- Observable result 2: a next-task plan exists for ladder-aware repricer completion with batches, risks, and proof rules.
- Observable result 3: the plan defines concrete success outputs and health checks for strategy quality.

## Reference material
- Research notes: `out/process_guides/repricing_tool/deep-research-report.md`
- Related repo files:
- `out/process_guides/repricing_tool/strategy-steps-v1.3.md`
- `out/process_guides/repricing_tool/master plans/masterplan_v10.md`
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/systems/H/live/h110_sku_lifecycle_log.csv`
- Prior tickets or plans:
- `project_control/TASK_QUEUE.md`
- `project_control/CURRENT_STATE.md`
