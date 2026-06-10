# Execution Batch 004

## Title
- Freshness hard-block recovery and guard unblocking

## Job
- remove the active guarded-run hard block:
  - `hard_block_reasons=["freshness_fail_active"]`
- prove the guarded run can move from `blocked` to `ready` without masking downstream warnings.

## Allowed files to change
- `scripts/one_off/BEF000_build_sales_truth_foundation.py`
- `tests/test_bef000_build_sales_truth_foundation.py`
- files inside `plans/active/b-e-f-sales-feedback-loop-v1/`

## Expectations

### Output 1 - boundary-safe proof plan
- use forced proof boundary for B-owned freshness recovery:
  - no overlapping B owner run
  - maintenance handoff when B owner is active
  - full `B_RUN_ONCE=1` proof cycle only after boundary is ready

### Output 2 - guarded run state transition
- rerun:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`
- target:
  - `guard_status=ready`
- if still blocked, output must name exact blocker and keep `next_action` explicit.

## Tests required
- boundary and proof planner evidence:
  - `python scripts/one_off/P002_plan_forced_proof_window.py --flow b --format json`
- guarded rerun evidence:
  - `python scripts/one_off/BEF004_run_sales_feedback_guarded_once.py`

## Proof required
- include lock/boundary evidence before manual B proof:
  - `out/systems/B/live/B_cycle.lock` state
  - maintenance marker states under `out/locks/`
- include guarded report delta:
  - previous `guard_status`
  - new `guard_status`
  - unchanged warnings (if any)
  - final `next_action`

## Execution result
- forced proof planner:
  - pass
  - current status: `boundary_or_pause_required` (active B owner detected)
- maintenance handoff:
  - request marker written with restart-drain ownership:
    - `requested_by=controlled_restart_gate`
    - `reason=overnight_restart_eval`
    - `request_id=BEF004_20260420T151131Z`
  - `maintenance.ready` matched request ID at boundary:
    - `B_READY|pid=6540|ts=2026-04-20T15:14:11Z|context=after cycle end|request_id=BEF004_20260420T151131Z`
  - side effect caught and recovered:
    - with request marker left in place, B supervisor repeatedly relaunched workers that exited at `before cycle start`
    - markers were cleared and B returned to normal cycle processing
- guarded rerun:
  - executed twice; still blocked on freshness hard block
- runtime ownership stop attempt:
  - direct stop of active B supervisor PID failed with `Access is denied`
  - full manual `B_RUN_ONCE=1` isolation could not be completed safely under current ownership permissions
- root-cause code fix added in this batch:
  - BEF000 freshness now reads ledger timestamp from `Date` before day-only `date`
  - lag measurement became more accurate:
    - before fix run: `930.25`
    - after fix run: `873.93`

## Live proof snapshot
- forced proof planner (`flow=b`) reports:
  - `proof_mode=boundary_safe_b_run_once`
  - `proof_window_status=boundary_or_pause_required`
  - active owner evidence:
    - `out/systems/B/live/B_supervisor.lock`
    - `pid=10060`
    - heartbeat moving during home-time run
- B loop recovery evidence after marker clear:
  - multiple full cycles reached:
    - `B_FINALIZE ran rc=0 wrote_health=true reason=cycle_complete`
  - latest cycle lock heartbeat kept moving
- guarded report (`out/analysis_reports/bef_sales_feedback_guarded_run_latest.json`):
  - `guard_status=blocked`
  - `hard_block_reasons=["freshness_fail_active"]`
  - `next_action=refresh_ledger_then_rerun_guarded_once`
  - metrics:
    - `freshness_fail_count=1`
    - `freshness_lag_minutes=873.93`
    - `actuals_summary_asin_rows=0`
    - `review_pending_outcome_rows=266`

## Sign-off
- `code fix applied`:
  - yes
- `isolated verification passed`:
  - yes
  - `python -m py_compile scripts/one_off/BEF000_build_sales_truth_foundation.py tests/test_bef000_build_sales_truth_foundation.py` -> pass
  - `pytest tests/test_bef000_build_sales_truth_foundation.py -q` -> pass (`3`)
- `live loop verification`:
  - partially confirmed:
    - B recovered to healthy full cycles after maintenance-marker cleanup
  - not yet proven for guard unblocking:
    - guarded run remains `blocked`
    - isolated `B_RUN_ONCE=1` boundary proof could not be executed due ownership stop permission failure

## Next step after sign-off
- define and implement a follow-up sub-batch for freshness hard-block resolution:
  - resolve B-owned freshness source contract so ledger freshness does not rely on day-only timestamps or unavailable stop privileges
  - rerun `BEF004` and require:
    - `guard_status=ready` for promotion
