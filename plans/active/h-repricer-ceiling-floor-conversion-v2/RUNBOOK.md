# Runbook

## Purpose
- What this plan or system does:
  - gives the working order for the next H repricer strategy phase:
    1. repair truth
    2. verify truth
    3. tune conversion
    4. verify results

## Standard run order
```powershell
# 1) Read current plan and baseline evidence
Get-Content plans\active\h-repricer-ceiling-floor-conversion-v2\CODING_PLAN.md
Get-Content plans\active\h-repricer-ceiling-floor-conversion-v2\DATA_REVIEW_2026-04-16.md

# 2) Run targeted tests after code changes
pytest tests\test_phase1_probe_engine.py -q
pytest tests\test_phase1_main_loop.py -q
pytest tests\test_phase1_storage.py -q
python -m py_compile scripts\phase1\phase1_probe_engine.py scripts\phase1\phase1_main_loop.py scripts\phase1\phase1_storage.py scripts\flows\A\A015_build_system_health_check.py

# 3) Read fresh runtime artifacts for proof
Get-Content out\h_ceiling_events.csv -TotalCount 5
Get-Content out\phase1_runtime_floor_snapshot_latest.csv -TotalCount 5
Get-Content out\h_strategy_outcome_daily.csv -TotalCount 20

# 4) Use the H forced proof window for sign-off, not vague next-cycle waiting
python scripts\one_off\P002_plan_forced_proof_window.py --flow h
.\run_H_isolation_status.bat
.\run_H_isolation_pause.bat
.\run_H_isolation_success.bat
python scripts\flows\A\A015_build_system_health_check.py --profile h --no-toast
.\run_H_isolation_resume.bat
Get-Content out\system_health_checklist.csv -TotalCount 20
Get-Content out\health_status.csv -Tail 5
```

## Validation steps
- Step 1:
  - confirm the active phase and its allowed files in `CODING_PLAN.md`
- Step 2:
  - run targeted tests and compile checks after each phase change
- Step 3:
  - confirm fresh H outputs meet the exact thresholds for that phase

## Expected outputs
- Output:
  - `out/h_ceiling_events.csv`
- Path:
  - `out/h_ceiling_events.csv`
- What good looks like:
  - effective ceiling is never below hard floor

- Output:
  - `out/phase1_runtime_floor_snapshot_latest.csv`
- Path:
  - `out/phase1_runtime_floor_snapshot_latest.csv`
- What good looks like:
  - latest SKU truth agrees with the ceiling contract

- Output:
  - `out/h_strategy_outcome_daily.csv`
- Path:
  - `out/h_strategy_outcome_daily.csv`
- What good looks like:
  - rollup counts are internally consistent and useful for operator review

## Health checks
- Check:
  - H ceiling/floor integrity
- Pass condition:
  - no effective ceiling below floor rows
- Warning condition:
  - isolated stale output or low sample warning only
- Fail condition:
  - any current effective ceiling below floor row

- Check:
  - H strategy daily rollup integrity
- Pass condition:
  - no impossible count relationships
- Warning condition:
  - stale daily output only
- Fail condition:
  - `at_floor_rows > decision_rows`, `below_break_even_rows > decision_rows`, or other impossible count contract failure

## Failure recovery
- If input is stale:
  - use the forced H proof window before falling back to passive waiting
- If output is missing:
  - inspect the H writer path, not downstream summaries
- If tests fail:
  - stop and fix the earliest failing owner stage before new monitoring
- If runtime ownership is unclear:
  - use the normal H owner artifacts and do not add manual overlapping runs

## Archive note
- What to preserve when this plan is finished:
  - final data review
  - final thresholds and proof counts
  - any new health-check names added for the H truth contract
