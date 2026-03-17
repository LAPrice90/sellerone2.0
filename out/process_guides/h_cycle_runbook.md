# H Cycle Runbook (Pricing Loop and Split Health Gate)

This guide explains how `scripts/run_H_pricing_cycle.py` runs, and how split health isolation controls live-write safety.

## 1) Core loop behavior

- H loop owns live-first lock path `out/systems/H/live/H_pricing_cycle.lock` (legacy mirror `out/H_pricing_cycle.lock`) to prevent double-run overlap.
- In Phase 1 pilot mode, H refreshes snapshots, aligns daily intel, rebuilds seller profile artifacts, then runs the pilot subprocess.
- The loop writes observability/state fields to the H live state path first:
- `out/systems/H/live/h_pricing_cycle_state.json`
- Legacy mirror path may still exist:
- `out/h_pricing_cycle_state.json`

## 1.1) Batch state machine (H-BATCH-001)

- H now writes a batch state file per run at:
- `out/systems/H/live/H_batch_state.json`
- Status transitions are explicit and use one `run_id`:
- `started -> collect_done -> compute_done -> validate_done -> published -> finalized`
- On failure, status is `failed` with a reason field.
- Every transition is also logged in `H_cycle.log` as:
- `h_batch_state_transition run_id=<id> from=<old> to=<new>`

## 1.2) Staged outputs (H-BATCH-002)

- Each run now creates a staged workspace:
- `out/systems/H/staged/<run_id>/`
- Phase 1 storage writes are redirected to:
- `out/systems/H/staged/<run_id>/data/*.csv`
- Stage pointer file:
- `out/systems/H/live/H_batch_stage_dir.txt`
- H publish flow now promotes staged Phase 1 tables into `data/*.csv` during publish commit.
- Before publish commit, Phase 1 table writes should land only in staged paths.

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

`out/systems/H/live/h_pricing_cycle_state.json` includes (legacy mirror `out/h_pricing_cycle_state.json`):
- `h_split_health_mode`
- `h_gate_fail_count`
- `h_gate_warn_count`
- `h_gate_block_live_writes`
- `h_gate_snapshot_utc`

Health readers must resolve H state path in this order:
- `out/systems/H/live/h_pricing_cycle_state.json`
- `out/h_pricing_cycle_state.json`

When `h_gate_block_live_writes=1`, pilot writes are blocked but the loop continues.

## 3.1) Lock liveness guardrail

- A015 now checks stale cycle locks directly:
- `h_cycle_stale_lock` (H lock exists but PID is dead -> FAIL)
- `e_cycle_stale_lock` (E lock exists but PID is dead -> FAIL)

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
