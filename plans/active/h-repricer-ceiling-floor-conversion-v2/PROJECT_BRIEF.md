# Project Brief

## Ticket
- Ticket name: `H repricer next phase - ceiling/floor truth and conversion`
- Date opened: `2026-04-16`
- Owner: `Codex`

## Business problem
- What is hurting today?
  - H is now stable enough to judge strategy, but the current evidence shows two truth problems before we can trust optimisation:
    - ceiling outputs still produce invalid states where the binding ceiling is below the hard floor
    - daily strategy rollups contain impossible counts such as `at_floor_rows > decision_rows`
- What decision or process is blocked?
  - We cannot safely tune crowded-seller repricing or judge whether the plan is working while the ceiling contract and rollup metrics are not fully truthful.

## Goal
- What should exist when this is done?
  - The previous H alignment plan is signed off and archived.
  - A new execution plan exists for:
    - repairing ceiling/floor truth at the earliest owner stage
    - repairing operator metrics so results are decision-grade
    - improving tactic conversion once the truth layer is fixed

## Why now
- Why is this worth doing now?
  - We now have enough live H data to move from stability work into strategy work.
  - The current sample is large enough to show what is working and what is not:
    - `multi_seller_ladder_cap` and `suppression_reactivation` no longer look falsely failed, but they still convert poorly
    - `raise_find_loss_ladder_cap` is the strongest current path
    - ceiling and rollup truth issues are now the main blockers to good decisions

## Constraints
- Existing system boundaries:
  - Root-cause first: fix earliest broken stage, not downstream output masking.
  - No Google Sheets changes unless explicitly asked.
  - No local DB changes to match sheets or vice versa.
  - No ad-hoc `A` runs unless explicitly asked by the user.
- Out of scope:
  - portfolio governor redesign
  - new sidecar loops
  - demand-learning expansion
  - sheet formatting or dashboard work
- Approval-sensitive areas:
  - any manual `A` run
  - any sheet write
  - any DB rewrite or historical backfill outside the owned H outputs

## Definition of success
- Observable result 1:
  - latest live H outputs no longer show `true_binding_ceiling_gbp < hard_floor_gbp`
- Observable result 2:
  - daily strategy rollups become internally consistent and pass integrity checks
- Observable result 3:
  - after truth repair, the crowded-ladder and suppression tactics show measurable conversion improvement against the 2026-04-16 baseline

## Reference material
- Research notes:
  - `plans/active/h-repricer-ceiling-floor-conversion-v2/DATA_REVIEW_2026-04-16.md`
- Related repo files:
  - `scripts/phase1/phase1_probe_engine.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - `scripts/flows/A/A015_build_system_health_check.py`
- Prior tickets or plans:
  - `plans/archive/2026/h-repricer-strategy-alignment-v1`
