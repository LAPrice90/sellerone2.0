# Incident Brief

## Ticket
- Incident name: `H ceiling/floor truth and strategy rollup integrity`
- Date opened: `2026-04-16`
- Owner: `Codex`

## Symptom
- What is visibly wrong?
  - Live H outputs still show effective ceilings below the hard floor.
  - Strategy daily rollups contain impossible counts.
- Where was it noticed?
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
- When was it first noticed?
  - during post-stability strategy review on `2026-04-16`

## Classification
- Data / Logic / Integration / Contract:
  - logic and contract

## Owning system
- Flow:
  - H
- Owner script:
  - `scripts/phase1/phase1_probe_engine.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
- Output or process owned:
  - ceiling decision contract
  - strategy outcome daily rollup

## Expected contract
- Expected path:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
- Expected schema or columns:
  - effective ceiling fields present where applicable
  - rollup count fields internally consistent
- Expected freshness:
  - live H cadence for runtime outputs
  - 24h for daily rollup
- Expected row or state rule:
  - effective ceiling must never be below floor
  - `at_floor_rows` and `below_break_even_rows` must never exceed `decision_rows`

## Actual state
- What exists now:
  - fresh outputs and large enough samples to judge the issue
- What is missing or wrong:
  - latest ceiling events: `8 / 58` conflicts
  - latest runtime floor snapshot: `11 / 89` conflicts
  - latest rollup contains impossible counts
- Evidence path:
  - `plans/active/h-repricer-ceiling-floor-conversion-v2/DATA_REVIEW_2026-04-16.md`

## Blast radius
- What downstream systems may be affected:
  - operator judgement of H strategy quality
  - A015 truthfulness for H strategy metrics
  - future repricer tuning decisions
- What must not be touched during first investigation:
  - sheets
  - DB ownership
  - unrelated scheduler logic

## Root-cause hypothesis
- Earliest likely broken stage:
  - ceiling source and strategy rollup ownership inside the H logic path
- Why this is the likely owner:
  - downstream outputs are already reflecting the conflict; they are not creating it

## Definition of done
- What proof must exist before the incident can be treated as fixed:
  - latest H outputs show `0` effective ceiling conflicts
  - daily rollup integrity checks pass
  - A015 shows the new checks as healthy on the next scheduled cycle
