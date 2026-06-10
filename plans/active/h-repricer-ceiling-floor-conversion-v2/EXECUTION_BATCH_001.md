# Execution Batch 001

## Purpose
- One-sentence outcome for this batch:
  - repair ceiling/floor truth and daily rollup integrity so the next strategy tuning phase works from trustworthy evidence

## Scope guardrails
- Only do:
  - truth contract repair
  - ceiling/floor integrity checks
  - daily rollup integrity repair
  - H-scoped health additions required for the new contracts
- Do not change:
  - Google Sheets
  - local DB
  - unrelated scheduler or owner-chain logic
  - crowded-ladder tuning rules beyond what is required to enforce the ceiling contract
- Do not add:
  - new sidecar loops
  - one-off logic inside daily loops
  - new operator metrics that are not tied to a clear health contract

## Files allowed to change
- `scripts/phase1/phase1_probe_engine.py`
- `scripts/phase1/phase1_main_loop.py`
- `scripts/phase1/phase1_storage.py`
- `scripts/flows/A/A015_build_system_health_check.py`
- `tests/test_phase1_probe_engine.py`
- `tests/test_phase1_main_loop.py`
- `tests/test_phase1_storage.py`

## Inputs to read first
- `AGENTS.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/PLAN.md`
- `plans/active/h-repricer-ceiling-floor-conversion-v2/CODING_PLAN.md`
- supporting files:
  - `plans/active/h-repricer-ceiling-floor-conversion-v2/DATA_REVIEW_2026-04-16.md`
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`

## Tasks
### Task 1
- Goal:
  - repair the daily strategy rollup so impossible count relationships cannot survive
- Files:
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - `scripts/flows/A/A015_build_system_health_check.py`
  - targeted tests
- Notes:
  - this is a truth task, not an optimisation task

### Task 2
- Goal:
  - enforce the effective ceiling contract so live binding ceilings cannot remain below the hard floor
- Files:
  - `scripts/phase1/phase1_probe_engine.py`
  - `scripts/phase1/phase1_main_loop.py`
  - `scripts/phase1/phase1_storage.py`
  - `scripts/flows/A/A015_build_system_health_check.py`
  - targeted tests
- Notes:
  - preserve raw conflict evidence for operator review

## Tests
- Command:
  - `pytest tests/test_phase1_probe_engine.py -q`
  - `pytest tests/test_phase1_main_loop.py -q`
  - `pytest tests/test_phase1_storage.py -q`
  - `python -m py_compile scripts/phase1/phase1_probe_engine.py scripts/phase1/phase1_main_loop.py scripts/phase1/phase1_storage.py scripts/flows/A/A015_build_system_health_check.py`
- Expected result:
  - targeted tests pass
  - compile passes

## Monitoring plan
- Live proof needed:
  - yes
- Forced proof window:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow h`
  - `.\run_H_isolation_pause.bat`
  - `.\run_H_isolation_success.bat`
  - `python scripts/flows/A/A015_build_system_health_check.py --profile h --no-toast`
  - `.\run_H_isolation_resume.bat`
- Artifacts to poll:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/system_health_checklist.csv`
- Poll cadence:
  - `+5 minutes`, `+10 minutes`, then every `+15 minutes` up to `+60 minutes`
- Success threshold:
  - `0` effective ceiling conflicts in latest H slice
  - `0` impossible daily rollup rows
  - forced H-scoped proof shows new checks as `ok`
- Timeout rule:
  - park as `pending next H proof window` with exact missing proof
- Fallback if forced proof is blocked:
  - record the exact ownership blocker, stale marker, or resume blocker before deferring
- Next phase after success:
  - Phase 2
- Notification mode:
  - passive
- User interruption threshold:
  - phase complete, contradiction, new/worse alert, timeout, or approval-required action

## Proof required
- Row counts:
  - latest ceiling conflict count
  - latest runtime effective ceiling conflict count
  - latest impossible daily rollup row count
- Health rows:
  - new A015 rows for ceiling/floor integrity and daily-rollup integrity
- Output files:
  - `out/h_ceiling_events.csv`
  - `out/phase1_runtime_floor_snapshot_latest.csv`
  - `out/h_strategy_outcome_daily.csv`
  - `out/system_health_checklist.csv`
- Notes:
  - do not call the batch complete until proof comes from fresh artifacts after the patch

## Completion checklist
- [ ] Scope held
- [ ] Files changed only in allowed set
- [ ] Tests passed
- [ ] Proof captured
- [ ] Reply file updated
