# Plan

## Goal
- Final outcome: complete the next H repricer strategy slice so live behavior matches the real plan, avoids blind multi-seller chasing, and emits outputs that prove whether the strategy is working.

## Non-goals
- Do not do:
- runtime-owner simplification work
- Google Sheets or local DB changes
- portfolio governor or pressure workflow expansion
- demand-ceiling learning rollout

## Current state
- What exists already:
- H runtime is live and fresh in the latest health snapshot.
- Current contract for live behavior is `strategy-steps-v1.3.md`.
- Target architecture is `masterplan_v10.md`.
- Current runtime emits usable decision evidence in:
- `out/phase1_runtime_floor_snapshot_latest.csv`
- `out/systems/H/live/h110_sku_lifecycle_log.csv`
- `out/systems/H/live/h110_sku_decision_log.csv`
- Suppression memory and temporary ceiling fields exist in the floor snapshot.
- Known pain points:
- The decision engine still centers on one best rival price.
- `REGAIN` writes go directly to the rival target and do not account for seller ladder depth.
- `RAISE_FIND_LOSS` can move up to ceiling, but there is no decision-grade output showing whether the raise worked or just invited another undercut.
- Suppression logic exists, but recent live rows show repeated no-write behavior rather than clear recovery outcomes.
- Sell-off states exist in code, but current live evidence shows almost no active controlled-exit behavior.
- Known alerts or reliability concerns:
- Latest H health rows inspected were OK.
- Strategy observability is incomplete:
- `out/h_ceiling_events.csv` exists and is populated, but quality gating is incomplete.
- `out/phase1_strategy_monitor.csv` is stale.
- `out/h_suppression_cases.csv` and `out/h_suppression_reactivation_log.csv` exist but key target fields are blank across current rows.

## Target state
- What changes:
- Add a scenario classifier that uses seller ladder depth and spacing, not just the single best rival.
- Split reset behavior into separate tactics:
- single-rival reset
- multi-seller ladder cap
- hold-share
- raise-find-loss
- controlled-exit-to-floor
- suppression-reactivation
- Add hold windows, retry budgets, and stop conditions so H does not immediately donate share or margin.
- Add measurement outputs that show tactic, seller ladder, chosen ceiling, hold window, and observed result.
- What stays the same:
- Hard floor remains absolute.
- Existing write gate and runtime-owner path remain intact.
- Suppression continues to use floor-safe and ceiling-safe clamps.

## Systems touched
- Flow(s): H
- Shared dependencies:
- A016 daily intel
- A018 floor table
- H130 observation publishing
- listing offer snapshots and seller snapshots
- Runtime or scheduler ownership concerns:
- Any future implementation must stay inside the canonical H owner chain and must not add sidecar loops that bypass H.

## File and output ownership
| Item | Owner script | Input or output | Path | Notes |
|---|---|---|---|---|
| Repricing decision state | `scripts/phase1/phase1_probe_engine.py` | logic | `scripts/phase1/phase1_probe_engine.py` | Needs ladder-aware scenario branch instead of single-rival-only logic |
| Repricing orchestration | `scripts/phase1/phase1_main_loop.py` | logic | `scripts/phase1/phase1_main_loop.py` | Needs seller-ladder classification, hold windows, and tactic reason codes |
| Observation publishing | `scripts/flows/H/H130_build_phase1_observation_sheet.py` | output | `scripts/flows/H/H130_build_phase1_observation_sheet.py` | Needs tactic-success visibility |
| Runtime floor snapshot | H runtime | output | `out/phase1_runtime_floor_snapshot_latest.csv` | Current truth view, but not enough by itself |
| Lifecycle log | H runtime | output | `out/systems/H/live/h110_sku_lifecycle_log.csv` | Current action evidence |
| Decision log | H runtime | output | `out/systems/H/live/h110_sku_decision_log.csv` | Current decision evidence |
| Ceiling event log | planned | output | `out/h_ceiling_events.csv` | Exists; needs decision-grade completeness checks |
| Strategy outcome log | planned | output | `out/h_strategy_outcome_log.csv` | New decision-grade tactic result log |
| Strategy rollup | planned | output | `out/h_strategy_outcome_daily.csv` | New daily summary for operator review |

## Data freshness and health checks
| Dataset | Freshness warn | Freshness fail | Health check | Notes |
|---|---:|---:|---|---|
| `out/phase1_runtime_floor_snapshot_latest.csv` | existing | existing | `h_phase1_runtime_floor_snapshot_latest_freshness` | Already live |
| `out/systems/H/live/h110_sku_lifecycle_log.csv` | existing H cadence | existing H cadence | existing H runtime freshness checks | Already live |
| `out/h_ceiling_events.csv` | 1 H cycle | 3 H cycles | new `h_ceiling_events_current` | Required by plan; quality gate needs to be enforced |
| `out/h_strategy_outcome_log.csv` | 1 H cycle | 3 H cycles | new `h_strategy_outcome_log_current` | Must prove tactic execution and outcome coverage |
| `out/h_strategy_outcome_daily.csv` | 24h | 48h | new `h_strategy_outcome_daily_current` | Operator-facing success rollup |

## Integration points
- APIs:
- Existing H offer snapshot and seller detail calls only
- Sheets:
- none
- Local DB:
- none
- CSV or file handoffs:
- seller ladder comes from `out/listing_offer_seller_snapshot_latest.csv`
- tactic truth comes from runtime floor snapshot plus lifecycle log

## Risks and mitigations
- Risk:
  - Multi-seller guard gets added as another downstream patch and hides the real state machine problem.
  - Mitigation:
  - Add scenario classification before price choice, not after chosen price.
- Risk:
  - Suppression rules stay partially implemented and continue producing no-write loops.
  - Mitigation:
  - Make suppression outputs mandatory and add health checks for blank target fields and repeated no-write loops.
- Risk:
  - Hold windows slow reaction too much on genuine one-rival regain cases.
  - Mitigation:
  - Split one-rival reset from crowded-ladder logic and measure each separately.
- Risk:
  - New outputs exist but do not actually show whether tactic logic worked.
  - Mitigation:
  - Require before/after fields, response window fields, and reason-coded result states.

## Proof rules
- What counts as code fix applied:
- scenario classifier, tactic rules, and output contracts are merged and unit-tested
- What counts as isolated verification passed:
- targeted tests cover single-rival reset, multi-seller ladder cap, undercut response hold, suppression recovery logging, and controlled-exit outputs
- What counts as live loop verification confirmed:
- new H cycles write populated strategy outcome rows
- ceiling event output exists and is current
- at least one live example is visible for each active tactic seen in runtime
- no blank mandatory tactic fields in the latest strategy outcome output

## Batch list
- Batch 001:
- Define the measurement contract.
- Activate and normalize output contracts: `out/h_ceiling_events.csv`, `out/h_strategy_outcome_log.csv`, `out/h_strategy_outcome_daily.csv`.
- Add schema and health checks for the new outputs.
- Batch 002:
- Add seller-ladder scenario classification.
- Replace one-rival blind regain with ladder-aware tactic selection.
- Add one-rival reset vs multi-seller ladder-cap behavior.
- Batch 003:
- Add undercut response windows, retry budgets, and stop conditions.
- Add controlled-exit reporting and suppression no-write loop detection.
- Validate live outcome rows after H cycles.

## Archive rule
- When this plan can move to archive:
- strategy outputs are live and populated
- ladder-aware tactics are implemented
- suppression and controlled-exit rows are visible and explainable
- live H evidence shows the tactic outputs are current and non-blank

## Active execution document
- Use `plans/active/h-repricer-strategy-alignment-v1/CODING_PLAN.md` as the current task-by-task coding sequence.
- It contains:
- baseline findings
- section ratings for coding/results/sample size
- monitored validation cadence, thresholds, and park rules for runtime proof
