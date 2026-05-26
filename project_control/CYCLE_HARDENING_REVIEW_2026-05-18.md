# Cycle Hardening Review - 2026-05-18

## Short Answer
- The cycles are recording why they die, but the proof is split across too many artifacts.
- H records the richest failure evidence, but the operator-facing terminal marker can still lose the real cause.
- A and B record enough to see the failed step, but not always enough child output to diagnose the actual root cause without re-running.
- The next level is not more manual fixes. It is one unified failure ledger, consistent cause codes, and stage-level recovery contracts.

## Evidence Reviewed
- Latest manifests under `out/manifests/A`, `out/manifests/B`, `out/manifests/E`, `out/manifests/H`, and `out/manifests/O`.
- H runtime artifacts under `out/systems/H/live`.
- Core manifest helpers in `scripts/core/run_manifest.py`.
- Cycle runners:
  - `scripts/cycles/run_A_all.py`
  - `scripts/cycles/run_B_cycle.py`
  - `scripts/cycles/run_B_supervisor.py`
  - `scripts/cycles/run_E_cycle.py`
  - `scripts/cycles/run_H_pricing_cycle.py`
  - `scripts/cycles/run_H_pricing_cycle_guarded.py`

## Current Failure Pattern
- A failed on 2026-05-17 and 2026-05-18 because producer scripts returned success or partial success without refreshing required outputs.
- A proof attempts from this Codex session also showed a diagnostic gap: A003 returned rc=1, but the A manifest did not include the child stderr that showed `PermissionError: secrets\\.env`.
- B is usually reaching the end of its loop, but recent B manifests still carry `fail=1 warn=1`. That means "completed" currently means the loop ended, not that the cycle was healthy.
- H latest real failure `H_20260518T103325Z` was a phase1 pilot max-runtime timeout. The child was still making progress, so this was not a stall. It exhausted the runtime budget while processing a large batch.
- H wrote strong detailed evidence in `phase1_pilot_wait_abnormal...json` and parent trace logs, but `H_cycle_last_terminal_info.txt` reduced the reason to `failure_code=LOOP_RC_1` with blank `failure_detail`.

## Highest-Value Hardening Recommendations

### 1. Create One Unified Failure Ledger
- Add `out/cycle_alerts/cycle_failure_events.jsonl` or CSV.
- Every A/B/E/H/O finalizer should append exactly one terminal row per run.
- Required fields:
  - `flow`
  - `run_id`
  - `started_utc`
  - `ended_utc`
  - `terminal_state`
  - `stage`
  - `step_name`
  - `cause_code`
  - `cause_detail`
  - `child_rc`
  - `elapsed_seconds`
  - `stdout_tail`
  - `stderr_tail`
  - `progress_tail`
  - `source_artifact`
  - `owner_restored`
  - `next_action`
- Health checks and MOT should read this ledger instead of reconstructing deaths from scattered files.

### 2. Standardize Cause Codes
- Replace free-text-only failure notes with a shared taxonomy.
- Suggested first set:
  - `OUTPUT_STALE`
  - `OUTPUT_MISSING`
  - `CHILD_RC_NONZERO`
  - `TIMEOUT_STALLED`
  - `TIMEOUT_PROGRESSING`
  - `MAINTENANCE_ABORT`
  - `PUBLISH_PROOF_MISSING`
  - `OWNER_CONTRACT_VIOLATION`
  - `LOCK_STALE`
  - `CREDENTIAL_ACCESS_DENIED`
  - `SHEET_GUARDRAIL`
  - `EXTERNAL_API_ERROR`
  - `INTERRUPTED_SIGNAL`
- Keep human detail, but gate automation on the code.

### 3. Fix H Terminal Cause Propagation
- H already writes the real pilot timeout evidence, but the latest terminal marker lost it.
- Change H finalization so `H_cycle_last_terminal_info.txt`, `H_run_state.json`, and the H manifest all carry the same failure cause.
- For the latest failure, the terminal marker should have said:
  - `failure_code=TIMEOUT_PROGRESSING`
  - detail including `phase1_pilot`, `elapsed_seconds=1802`, `effective_max_timeout_seconds=1800`, and the latest progress tail.

### 4. Stop Killing H Work That Is Still Progressing Without a Resume Plan
- The latest H failure was max runtime while progress was still advancing.
- That is a capacity/budget problem, not a deadlock.
- Better options:
  - dynamically extend budget from progress rate and remaining SKU count
  - split H pilot into smaller bounded chunks
  - commit a checkpoint after each SKU group
  - resume next cycle from the last completed SKU instead of restarting the whole pilot stage
- The target is: timeout kills only stalled work, not active useful work.

### 5. Add Child Output Tails to A Manifests
- A currently records rc and verification status, but non-receipt child failures do not include stdout/stderr tails in the manifest.
- A003 should have captured the `secrets\\.env` permission error directly in the A manifest.
- Add safe truncated `stdout_tail` and `stderr_tail` to every failed child step.

### 6. Separate "Completed" From "Healthy"
- B can end with `final_state=completed` while health still has FAIL/WARN.
- Keep `final_state=completed` if the loop reached its boundary, but add:
  - `gate_state=pass|warn|fail|not_run`
  - `completed_with_gate_fail=true|false`
  - `blocking_checks=...`
- This avoids false reassurance and makes repeated failures visible without reading every checklist.

### 7. Reclassify Maintenance Aborts
- B steps interrupted by A maintenance are currently recorded as failed steps in some manifests.
- These should be `step_status=maintenance_aborted` with `cause_code=MAINTENANCE_ABORT`.
- That keeps real failures separate from intentional owner handoff.

### 8. Centralize Windows PID and Lock Truth
- Several scripts have their own `_pid_alive` logic.
- Some Windows checks can return access denied even when a process exists.
- Move process checks into one shared helper and treat access-denied as "may be alive" for safety.
- Use it from A, B supervisor, B worker, E, and H.

### 9. Add a Cycle Autopsy Tool
- Build `scripts/tools/cycle_autopsy.py`.
- Inputs:
  - `--flow A|B|E|H|all`
  - `--run-id latest`
- Output:
  - one JSON summary
  - one CSV row appended to the failure ledger
  - plain-text operator summary for MOT
- It should read manifests, runtime status, terminal markers, heartbeat, parent trace, watchdog markers, and recent stderr tails.

### 10. Add Fault-Injection Tests
- Add tests that intentionally simulate:
  - child rc nonzero
  - stale output after rc 0
  - timeout while stalled
  - timeout while still progressing
  - maintenance abort
  - missing result marker
  - permission denied on secrets/env
  - publish marker mismatch
  - hard exit or signal
- Each test should assert that the unified failure ledger receives the correct `cause_code`.

## Suggested Build Order
1. Add shared failure event writer and cause-code constants.
2. Add A child stdout/stderr tails for nonzero child steps.
3. Patch H terminal marker to preserve the real phase/stage failure reason.
4. Make H pilot timeout distinguish `TIMEOUT_STALLED` from `TIMEOUT_PROGRESSING`.
5. Add B `gate_state` and maintenance-abort classification.
6. Add `cycle_autopsy.py`.
7. Add fault-injection tests for A/B/H first, then E.

## Operator-Level Answer
- We are not blind today.
- We are recording enough evidence to diagnose most deaths.
- We are not yet recording it in one consistent place with consistent cause codes.
- That is why the work feels like whack-a-mole: the evidence exists, but the system is not turning it into repeatable hardening tasks automatically.

## Implementation Update - 2026-05-18T11:55:18Z
- Phase 1 is implemented: shared failure ledger writer added at `scripts/core/cycle_failure_events.py`.
- New ledger target: `out/cycle_alerts/cycle_failure_events.csv`.
- Schema guard added and documented in `project_control/OUTPUT_SCHEMA_CHECKS.md`.
- A now records truncated child `stdout_tail` and `stderr_tail` for the known failure-prone producer steps and writes a terminal failure event when the A manifest ends failed or partial.
- H now preserves classified terminal causes before final cleanup can collapse them to `LOOP_RC_*`.
- H timeout classification now distinguishes:
  - `TIMEOUT_PROGRESSING` for max-runtime timeout while progress is still moving.
  - `TIMEOUT_STALLED` for true stall timeout.
- H failed manifests now write a terminal failure event to the shared ledger.
- Isolated verification passed:
  - `python -m py_compile scripts/core/cycle_failure_events.py scripts/core/run_manifest.py scripts/cycles/run_A_all.py scripts/cycles/run_H_pricing_cycle.py`
  - `python -m pytest tests/test_cycle_failure_events.py tests/test_a_split_health_modes.py tests/test_h_worker_lifecycle_contract.py -q`
  - Result: 59 passed.
- Live-loop verification is not yet proven. The next failed A or H terminal run after this change should create or update the shared ledger row.

## Implementation Update - 2026-05-18T12:05:16Z
- B manifests now separate loop completion from health truth:
  - `final_state` still means whether the B loop reached its boundary.
  - `gate_state` now records `pass`, `warn`, `fail`, or `not_run`.
  - `completed_with_gate_fail` marks the case where B completed but the B gate still failed.
  - `blocking_checks` lists the failed B checks.
- B maintenance-requested child exits are now classified as `maintenance_aborted` with `verification_status=maintenance_abort`, instead of ordinary failed steps.
- Added `scripts/tools/cycle_autopsy.py` for read-only manifest autopsy across A/B/E/H/O, with optional ledger upsert.
- Read-only autopsy against current manifests confirmed the repeated H root cause:
  - latest H manifest `H_20260518T110904Z` failed as `TIMEOUT_PROGRESSING`.
  - The child was still progressing but exhausted the max runtime budget.
- H timeout hardening added:
  - max progress grace default increased from 900 seconds to 2700 seconds.
  - This keeps true stall timeout behavior unchanged while allowing moving work more bounded time.
- Added health-check schema coverage:
  - `shared_cycle_failure_ledger_schema` checks the shared failure ledger header contract.
- Isolated verification passed:
  - compile passed for changed core, A, B, H, autopsy, and health-check files.
  - focused pytest passed, 77 tests.
- Live-loop verification is still not yet proven because active B/H owner processes may have started before this code was loaded.

## Implementation Update - 2026-05-18T13:47:36Z
- The 13:30 local B check ran and was recorded in `project_control/DUE_CHECK_REGISTER.csv`.
- Result: not yet proven. B continued to complete cycles, but the active B worker pid 3808 still started at `2026-05-18T11:30:33Z`, before the B manifest gate-state patch loaded.
- The latest checked B manifest, `B_20260518T134355Z`, ended at `2026-05-18T13:51:47Z` and still lacked the new gate fields.
- We did not use the global `maintenance.requested` restart-drain marker because active H and F owners were present. That marker is cross-flow and would widen a B-only proof.
- Hardening added:
  - `out/locks/b_cycle.maintenance` can now request B-only restart drain when its text includes `action=restart_drain`, `exit_after_drain=1`, or `restart_drain=1`.
  - `scripts/one_off/P002_plan_forced_proof_window.py` now checks active H and F ownership for B proof planning and warns against global `maintenance.requested` for B-only proof while those owners are active.
- Isolated verification passed:
  - `python -m py_compile scripts/cycles/run_B_cycle.py scripts/one_off/P002_plan_forced_proof_window.py`
  - `python -m pytest tests/test_b_manifest_gate_state.py tests/test_p002_plan_forced_proof_window.py -q`
  - Result: 11 passed.
- Broader focused verification passed after aligning stale A015 test fixtures to current contracts:
  - `python -m pytest tests/test_cycle_failure_events.py tests/test_a_split_health_modes.py tests/test_h_worker_lifecycle_contract.py tests/test_a015_health_check_runtime.py tests/test_b_manifest_gate_state.py tests/test_cycle_autopsy.py tests/test_p002_plan_forced_proof_window.py -q`
  - Result: 114 passed, 1 existing `datetime.utcnow()` deprecation warning.
- Live-loop verification remains pending until a fresh B owner loads the new code.
