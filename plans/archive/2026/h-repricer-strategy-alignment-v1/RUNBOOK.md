# Runbook

## Purpose
- Keep H strategy alignment truthful and decision-grade by separating:
  - tactic failed
  - no-proof timeout (`expired`)
  - non-action hold (`aborted`)
- Maintain a repeatable operator path for validation and next-phase tuning.

## Standard run order
```powershell
# 1) Read current artifacts (default source of truth)
Get-Content out\system_health_checklist.csv -Tail 40
Get-Content out\h_strategy_outcome_daily.csv -Tail 40
Get-Content out\h_strategy_outcome_log.csv -Tail 40

# 2) If historical strategy rows need normalization
python scripts\one_off\H162_rebuild_strategy_outcome_daily.py --dry-run
python scripts\one_off\H162_rebuild_strategy_outcome_daily.py

# 3) Validate patch safety
python -m py_compile scripts\phase1\phase1_main_loop.py
python -m py_compile scripts\flows\H\H110_run_phase1_h_pilot.py
python -m py_compile scripts\one_off\H162_rebuild_strategy_outcome_daily.py
python -m pytest tests\test_phase1_main_loop.py -k "share_hold_non_action_stop_returns_aborted or emit_strategy_outcome_reclassifies_non_action_headroom_to_share_hold or close_pending_strategy_outcome" -q
```

## Validation steps
- Step 1:
  - Confirm Task 7 proof in `out/h_strategy_outcome_log.csv`:
    - reason code `OUTCOME_RECLASSIFIED_NON_ACTION_HOLD` exists
    - those rows are `scenario_type=share_hold`
    - `tactic_success_state` trends to `aborted` instead of `failed`
- Step 2:
  - Confirm `H162` dry-run returns:
    - `converted_failed_timeouts_to_expired=0`
    - `converted_non_action_expired_to_aborted=0`
    - `converted_non_action_failed_to_aborted=0`
    - `converted_floor_bound_failed_to_aborted=0`
  - after a real run has already been applied
- Step 3:
  - Confirm checklist refresh in next scheduled A cycle:
    - `h_strategy_expired_share_multi_seller_ladder_cap` is `ok`
    - `h_strategy_expired_share_single_rival_reset` is `ok`

## Expected outputs
- Output:
  - strategy daily rollup with truth-split terminal counters
- Path:
  - `out/h_strategy_outcome_daily.csv`
- What good looks like:
  - `expired_rows` and `aborted_rows` populated with stable schema columns

- Output:
  - strategy event log with reclassification reason code
- Path:
  - `out/h_strategy_outcome_log.csv`
- What good looks like:
  - non-action hold rows carry `OUTCOME_RECLASSIFIED_NON_ACTION_HOLD`

- Output:
  - health checklist checks for strategy expired-share
- Path:
  - `out/system_health_checklist.csv`
- What good looks like:
  - expired-share checks are `ok` after backfill-aware refresh

## Health checks
- Check:
  - `h_strategy_expired_share_multi_seller_ladder_cap`
- Pass condition:
  - status `ok`
- Warning condition:
  - status `warn`
- Fail condition:
  - status `fail`

- Check:
  - `h_strategy_expired_share_single_rival_reset`
- Pass condition:
  - status `ok`
- Warning condition:
  - status `warn`
- Fail condition:
  - status `fail`

- Check:
  - `h_strategy_no_write_failed_streak_*`
- Pass condition:
  - status `ok`
- Warning condition:
  - one or more streak checks `warn`
- Fail condition:
  - one or more streak checks `fail`

## Failure recovery
- If input is stale:
  - treat checklist as stale when it is older than the last strategy code/backfill change timestamp
- If output is missing:
  - rebuild daily via `H162` and re-check required columns
- If tests fail:
  - stop and fix the specific failing test path before running live validation
- If runtime ownership is unclear:
  - do not run overlapping manual loop scripts; check `out/systems/H/live/H_runtime_status.json` and scheduler state first

## Archive note
- Preserve when this plan is complete:
  - `CODING_PLAN.md`
  - `PLAN_STATUS.md`
  - `DATA_CONTRACTS.md`
  - this `RUNBOOK.md`
  - one proof snapshot set from:
    - `out/h_strategy_outcome_log.csv`
    - `out/h_strategy_outcome_daily.csv`
    - `out/system_health_checklist.csv`
