# H Cycle Runbook (Pricing Loop and Split Health Gate)

This guide explains how `scripts/run_H_pricing_cycle.py` runs, and how split health isolation controls live-write safety.

## 1) Core loop behavior

- H loop owns `out/H_pricing_cycle.lock` to prevent double-run overlap.
- In Phase 1 pilot mode, H refreshes snapshots, aligns daily intel, rebuilds seller profile artifacts, then runs the pilot subprocess.
- The loop always keeps writing observability/state fields to `out/h_pricing_cycle_state.json`.

## 2) Split health isolation modes

- `H_SPLIT_HEALTH_MODE=legacy|shadow|split` (rollout default is `shadow`).
- `H_SPLIT_CHECKLIST_PATH=out/cycle_alerts/checklist_H_split.csv`.
- `H_HEALTH_INTERVAL_SECONDS` controls how often profile-H health is refreshed (default `900`).
- `H_HEALTH_FAIL_CLOSED=1` means missing or unreadable H snapshot blocks live writes in `split` mode.

Mode behavior:
- `legacy`: no H split gate applied.
- `shadow`: run `A015 --profile h` on interval, log candidate gate decision, do not block writes.
- `split`: run `A015 --profile h` on interval, and force pilot subprocess to `--read-only` when H FAIL > 0 or when fail-closed applies.

## 3) Gate fields written to state

`out/h_pricing_cycle_state.json` includes:
- `h_split_health_mode`
- `h_gate_fail_count`
- `h_gate_warn_count`
- `h_gate_block_live_writes`
- `h_gate_snapshot_utc`

When `h_gate_block_live_writes=1`, pilot writes are blocked but the loop continues.

## 4) Shadow compare and cutover tracker

- `out/cycle_alerts/split_shadow_compare.csv` records B and H shadow observations.
- `out/cycle_alerts/split_shadow_state.json` tracks:
- `b_match_streak`
- `h_clean_streak`
- `ready_for_cutover`
- Automatic cutover: when both streaks reach 10, `ready_for_cutover=true`; H effective mode auto-switches from `shadow` to `split`.

## 5) Manual rollback

If needed, revert to legacy immediately:
- `set B_SPLIT_HEALTH_MODE=legacy`
- `set H_SPLIT_HEALTH_MODE=legacy`

Keep split artifacts for diagnosis after rollback.
