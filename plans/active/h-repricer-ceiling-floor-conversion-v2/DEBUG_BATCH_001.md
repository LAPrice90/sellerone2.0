# Debug Batch 001

## Problem
- Exact symptom:
  - H can still publish effective ceiling values below floor and daily rollups with impossible counts

## Classification
- Data / Logic / Integration / Contract:
  - logic and output contract

## Owner
- Flow:
  - H
- Owner script:
  - `scripts/phase1/phase1_probe_engine.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
- Owned output or process:
  - effective ceiling decision path
  - strategy outcome daily rollup

## Expected contract
- Path:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
- Schema or shape:
  - effective ceiling never below floor
  - rollup counts internally consistent
- Freshness:
  - normal H cadence
- Coverage or row expectation:
  - all fresh rows obey the contract

## Actual state
- What is wrong vs expected:
  - latest ceiling run contains `8 / 58` effective conflicts
  - latest runtime slice contains `11 / 89` effective conflicts
  - latest daily rollup contains impossible `at_floor_rows` counts
- Evidence:
  - `plans/active/h-repricer-ceiling-floor-conversion-v2/DATA_REVIEW_2026-04-16.md`

## Root cause
- Earliest broken stage:
  - H logic path before outputs are written
- Why:
  - output files are faithfully exposing the bad state instead of creating it

## Scope guardrails
- Only inspect or change:
  - H ceiling logic
  - H rollup logic
  - H storage schema rules
  - H-scoped A015 checks
- Do not touch:
  - sheets
  - DB sync
  - unrelated loop ownership
- Do not mask downstream output:
  - preserve raw conflict evidence if the effective ceiling contract is repaired

## Fix plan
- File to change:
  - `scripts/phase1/phase1_probe_engine.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - `scripts/flows/A/A015_build_system_health_check.py`
- Expected behavior after fix:
  - raw ceiling conflicts remain visible
  - effective ceiling never lands below floor
  - impossible rollup counts are blocked by logic and surfaced by health checks

## Tests and proof
- Targeted test:
  - phase1 probe, main loop, and storage tests
- Pipeline rerun:
  - not ad-hoc A by default; use the H forced proof window before falling back to a later scheduler run
- Forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- Health check:
  - new H-scoped integrity rows in `out/system_health_checklist.csv`
- Output sample:
  - latest H outputs after patch

## Acceptance criteria
- Root cause fixed at owner or source stage
- Health check passes
- No regression introduced in adjacent flow
