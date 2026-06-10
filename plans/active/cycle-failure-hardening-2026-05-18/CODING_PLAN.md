# Cycle Failure Hardening - 2026-05-18

## Current Phase
- Status: parked pending next proof window.
- Started UTC: 2026-05-18T11:45:38Z.
- Last updated UTC: 2026-05-18T13:55:54Z.
- Owner: Codex.

## Problem
- Cycle failure evidence exists, but it is split across manifests, runtime state files, logs, and terminal markers.
- A records failed step status, but nonzero child output is often missing from the manifest, so diagnosis needs extra digging.
- H can detect a rich timeout cause internally, but final terminal files can collapse the reason to weak `LOOP_RC_*` text.
- The goal is to stop guessing after a dead cycle by writing one clear terminal failure row per failed run.

## Scope
- Allowed files:
  - `scripts/core/cycle_failure_events.py`
  - `scripts/core/run_manifest.py`
  - `scripts/cycles/run_A_all.py`
  - `scripts/cycles/run_B_cycle.py`
  - `scripts/cycles/run_H_pricing_cycle.py`
  - `scripts/tools/cycle_autopsy.py`
  - `scripts/one_off/P002_plan_forced_proof_window.py`
  - focused tests under `tests/`
  - `project_control/CYCLE_HARDENING_REVIEW_2026-05-18.md`
  - `project_control/OUTPUT_SCHEMA_CHECKS.md`
  - this plan file
- Do not edit Google Sheets.
- Do not align local DB to Sheets.
- Do not run overlapping A, B, or H loop work.
- New logging is observation-only until it has isolated proof.

## Implementation Phases
- Phase 1: add shared failure ledger writer and schema validation. Status: complete.
- Phase 2: add A child stdout/stderr tails to failed manifest steps and write terminal A failure events. Status: complete.
- Phase 3: preserve H terminal failure cause, especially timeout-progressing versus timeout-stalled, and write terminal H failure events. Status: complete.
- Phase 4: focused isolated tests and compile checks. Status: complete.
- Phase 5: B completion-vs-health truth and maintenance-abort classification. Status: complete.
- Phase 6: first cycle autopsy reader. Status: complete.
- Phase 7: H timeout-progressing hardening. Status: complete.
- Phase 8: record live proof status and next verifier without claiming live runtime success early. Status: in progress; 13:30 local B check recorded as pending fresh owner.
- Phase 9: add scoped B-only restart-drain planning so B proof does not depend on the global maintenance marker when H or F is active. Status: code complete; isolated verification passed; live owner reload not yet proven.

## Test Plan
- Run focused tests:
  - `python -m pytest tests/test_cycle_failure_events.py tests/test_a_split_health_modes.py tests/test_h_worker_lifecycle_contract.py -q`
- Compile changed runners:
  - `python -m py_compile scripts/core/cycle_failure_events.py scripts/core/run_manifest.py scripts/cycles/run_A_all.py scripts/cycles/run_H_pricing_cycle.py`
- Result at 2026-05-18T11:55:18Z:
  - compile passed
  - focused pytest passed, 59 tests
- Result at 2026-05-18T12:05:16Z:
  - compile passed for changed core, A, B, H, autopsy, and health-check files
  - focused pytest passed, 77 tests
- Result at 2026-05-18T13:47:36Z:
  - compile passed for `scripts/cycles/run_B_cycle.py` and `scripts/one_off/P002_plan_forced_proof_window.py`
  - focused pytest passed, 11 tests:
    - `tests/test_b_manifest_gate_state.py`
    - `tests/test_p002_plan_forced_proof_window.py`
- Result at 2026-05-18T13:55:54Z:
  - broader focused pytest passed, 114 tests:
    - `tests/test_cycle_failure_events.py`
    - `tests/test_a_split_health_modes.py`
    - `tests/test_h_worker_lifecycle_contract.py`
    - `tests/test_a015_health_check_runtime.py`
    - `tests/test_b_manifest_gate_state.py`
    - `tests/test_cycle_autopsy.py`
    - `tests/test_p002_plan_forced_proof_window.py`
  - one existing warning remains: `datetime.utcnow()` deprecation in `scripts/cycles/run_B_cycle.py`.

## Live Proof Plan
- Isolated tests can prove the code paths.
- Live loop verification is separate and not yet proven by isolated tests.
- A live proof remains covered by `project_control/DUE_CHECK_REGISTER.csv` row `A_MOT_DAILY_CHAIN_20260518_LIVE_PROOF`.
- H live proof requires H-owned proof: pause scheduler ownership first, run guarded one-shot, read scoped health after finalization, then restore scheduler ownership.

## Monitoring
- Artifact: `out/cycle_alerts/cycle_failure_events.csv`.
- Success threshold: first failed A or H terminal run after 2026-05-18T11:55:18Z writes one row with cycle, run_id, final_state, cause_code, cause_detail, step/stage, rc, manifest path, and health path.
- Poll cadence for live validation if started: first check +5 minutes, second +10 minutes, then every +15 minutes up to +60 minutes.
- Timeout rule: if no failed terminal run occurs inside the bounded proof window, keep status as isolated verification passed and live failure-ledger verification not yet proven.
- Automatic next step after isolated proof: use the next safe A or H flow-owned proof window only if it does not overlap active ownership.
- Durable follow-up: `project_control/DUE_CHECK_REGISTER.csv` row `CYCLE_FAILURE_LEDGER_FIRST_LIVE_PROOF`.
- Additional durable follow-ups:
  - `project_control/DUE_CHECK_REGISTER.csv` row `B_GATE_STATE_20260518_LIVE_PROOF`
  - `project_control/DUE_CHECK_REGISTER.csv` row `H_TIMEOUT_PROGRESSING_20260518_FRESH_OWNER_PROOF`

## 13:30 Local Check - 2026-05-18
- Due-check sweep ran at local 13:32 / UTC 12:32.
- `out/manifests/B/2026-05-18/B_20260518T121517Z.json` ended at `2026-05-18T12:30:33Z` with final_state `completed`, but it did not contain the new B gate fields.
- Active B owner lock still showed pid 3808 started at `2026-05-18T11:30:33Z`, before the `2026-05-18T12:05:16Z` code change loaded.
- Result: B live proof is not yet proven. This is not a code failure; it is an old owner still running old loaded code.
- Next verifier: a B manifest from an owner started after `2026-05-18T12:05:16Z`, or a boundary-safe B proof after maintenance handoff.

## Monitored Validation - B Fresh Owner
- Started UTC: 2026-05-18T12:40:00Z.
- Mode: passive monitored validation.
- Poll cadence: first check +5 minutes, second check +10 minutes, then every +15 minutes until +60 minutes.
- Artifact: `out/manifests/B/2026-05-18`.
- Success condition: latest B manifest includes `gate_state`, `gate_rc`, `gate_fail_count`, `gate_warn_count`, `completed_with_gate_fail`, and `blocking_checks`.
- Safety rule: do not use the global restart-drain marker while active H and F owners are present, because that marker is cross-flow and would widen the B-only proof.
- Timeout rule: if no fresh-owner manifest appears inside the window, leave the status as `parked pending next proof window` and keep the next verifier as a fresh B owner or a scoped B-only restart path.

## Monitored Validation Result - 2026-05-18
- Completed UTC: 2026-05-18T13:56:35Z.
- Latest checked B manifest: `out/manifests/B/2026-05-18/B_20260518T134355Z.json`.
- Latest checked B manifest ended at `2026-05-18T13:51:47Z`.
- Result: timeout. The latest manifest still lacks `gate_state`, `gate_rc`, `gate_fail_count`, `gate_warn_count`, `completed_with_gate_fail`, and `blocking_checks`.
- Owner truth: `out/systems/B/live/B_cycle.lock` still showed pid 3808 with start `2026-05-18T11:30:33Z`, so the B worker did not reload after the code change.
- Safety decision: the global restart-drain marker was not used because active H and F owners were present. Using that marker for a B-only proof would widen the runtime impact.
- Status: parked pending next proof window.
- Next verifier: a B manifest from a fresh owner, or a scoped B-only restart path that does not pause H or F.

## Scoped B Restart-Drain Hardening - 2026-05-18
- Change: `scripts/cycles/run_B_cycle.py` now treats existing `out/locks/b_cycle.maintenance` text containing `action=restart_drain`, `exit_after_drain=1`, or `restart_drain=1` as a B-only restart-drain request.
- This reuses the existing B-only marker instead of creating a new marker file.
- Change: `scripts/one_off/P002_plan_forced_proof_window.py` now checks active H and F ownership when planning B proof and warns not to use the global `maintenance.requested` marker for B-only proof while those owners are active.
- Planner output now points to scoped `b_cycle.maintenance` before any `B_RUN_ONCE` proof.
- Test maintenance: A015 runtime tests were updated to match current contracts for manifest truth fields, latest-cycle B fail stats, and the logger callback required by `_phase1_rollout_checks`.
- Live status: not yet loaded by the current B owner because pid 3808 started before this patch. The next fresh B owner will be able to use this scoped path.

## Next Scheduled Proof Opportunity
- Scheduler evidence: `AMZ Controlled Restart` next run is `2026-05-19 02:10:00` local.
- UTC equivalent: `2026-05-19T01:10:00Z`.
- Proof check time: `2026-05-19 02:40:00` local / `2026-05-19T01:40:00Z`.
- Artifact to inspect: `out/manifests/B/2026-05-19`.
- Success condition: the latest finalized B manifest is from a fresh owner and includes `gate_state`, `gate_rc`, `gate_fail_count`, `gate_warn_count`, `completed_with_gate_fail`, and `blocking_checks`.
- Failure action: if no fresh B owner appears, inspect `out/locks/restart_control/restart_controller.latest.json` for skipped restart blockers before attempting any manual B proof.

## Ad Hoc Check - 2026-05-18T14:45:10Z
- Local time: 2026-05-18 15:45.
- Latest B manifest: `out/manifests/B/2026-05-18/B_20260518T142724Z.json`.
- Latest B manifest ended at `2026-05-18T14:42:16Z`.
- Result: still not proven. The manifest still lacks `gate_state`, `gate_rc`, `gate_fail_count`, `gate_warn_count`, `completed_with_gate_fail`, and `blocking_checks`.
- Owner truth: `out/systems/B/live/B_cycle.lock` still shows pid 3808, start `2026-05-18T11:30:33Z`, heartbeat `2026-05-18T14:45:10Z`.
- Restart truth: `AMZ Controlled Restart` has not run again since `2026-05-18 02:10:01`; next scheduled run remains `2026-05-19 02:10:00` local.
