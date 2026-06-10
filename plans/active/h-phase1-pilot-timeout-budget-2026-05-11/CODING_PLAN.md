# H Phase1 Pilot Timeout Budget - 2026-05-11

## Status
- Phase: implementation
- Owner: Codex
- Started: 2026-05-11
- Scope: H cycle phase1 pilot parent watchdog only

## Verification Status
- Code fix applied: yes
- Isolated tests passed: `python -m pytest tests\test_h_worker_lifecycle_contract.py tests\test_h110_market_payload_snapshot_floor.py -q`
- Isolated test result: 50 passed
- Runtime proof status: forced proof window required
- Changed at: 2026-05-11T08:28:34Z
- Latest H health snapshot at: 2026-05-11T08:15:20Z
- Scheduler pause attempt: blocked because current shell is not elevated/admin
- Proof trigger: user opens an elevated/admin shell or otherwise grants an H scheduler ownership pause window
- Next verifier: H controlled one-shot after scheduler ownership pause

## Problem
Morning MOT found `H_20260511T062019Z` failed in `phase1_pilot`.

Evidence:
- Failure artifact: `out/systems/H/live/phase1_pilot_wait_abnormal.20260511T062019Z.1778480533889259200.json`
- Manifest: `out/manifests/H/2026-05-11/H_20260511T062019Z.json`
- Failure reason: `phase1 pilot step timeout reason=max_runtime`
- Parent watchdog killed the child after about `900.77` seconds.
- The child was still making fresh progress: `stalled_seconds=5.05`.
- The progress tail was at SKU `8M-LM6B-F2Q5`, item `42` in the pilot run.
- Later live evidence showed the same zero-row market-payload branch can finish successfully when not killed at the max-runtime boundary.

Root-cause theory:
- The phase1 pilot max-runtime budget is fixed at 900 seconds while the pilot can still be processing valid SKU work.
- The parent watchdog treats total elapsed time as a hard stop even when the child has recent progress.
- This can kill a healthy pilot near the end of a large pilot batch.

This is not a downstream output formatting issue and should not be fixed by hiding the failed health result.

## Allowed Files
- `scripts/cycles/run_H_pricing_cycle.py`
- `tests/test_h_worker_lifecycle_contract.py`
- `plans/active/h-phase1-pilot-timeout-budget-2026-05-11/CODING_PLAN.md`

## Implementation Plan
1. Add a bounded progress-grace path to the H phase1 pilot parent watchdog.
2. Keep the existing stall timeout behavior.
3. Keep the total runtime bounded with an explicit max progress-grace cap.
4. Log every progress-grace extension so operator evidence stays visible.
5. Add focused unit tests for the watchdog budget decision.

## Test Plan
- Run focused H watchdog tests.
- Run existing market-payload snapshot-floor tests to confirm the zero-row branch behavior is still unchanged.

## Runtime Proof Plan
Required proof path after code and isolated tests:
- Pause H scheduler ownership first.
- Run one guarded H controlled success proof.
- Confirm terminal truth for the controlled run.
- Resume H scheduler ownership.
- Confirm scheduler ownership is restored.

If local permissions prevent scheduler pause/resume, status must remain:
- `Verification status: Forced proof window required`
- `Next verifier: H controlled one-shot after scheduler ownership pause`

## Monitoring Target
- Artifact: latest `out/manifests/H/YYYY-MM-DD/H_*.json`
- Trigger: run after the H scheduler is paused and controlled mode is active.
- Success condition: next controlled H proof reaches a terminal success state without `phase1_pilot` max-runtime failure.
- Failure action: inspect the new failure artifact and decide whether the remaining cause is stall, data, or workload budget.

## MOT Continuation - 2026-05-11T08:48Z
- User asked to proceed after full MOT.
- H timeout root cause remains the fixed parent watchdog max-runtime budget while child progress is still fresh.
- Focused H verification rerun passed: `python -m pytest tests\test_h_worker_lifecycle_contract.py tests\test_h110_market_payload_snapshot_floor.py -q` -> `50 passed`.
- Forced proof planner rerun: `python scripts\one_off\P002_plan_forced_proof_window.py --flow h --format json`.
- Proof window status: `pause_required`.
- Current H proof blocker: H scheduler task `AMZ H Cycle` is enabled, active H lock points at run `20260511T083518Z`, and controlled mode is not active.
- This shell is not elevated/admin, so it cannot safely run `.\run_H_isolation_pause.bat` or `.\run_H_isolation_resume.bat`.
- Latest terminal evidence at this point is still not proof of the code change: `out/systems/H/live/H_cycle_last_terminal_info.txt` reports run `20260511T081520Z`, `state=failed`, `stage=phase1_pilot`, `failure_code=LOOP_RC_1`.

Required next H verifier:
- Exact trigger: elevated/admin H isolation window.
- Exact sequence: `.\run_H_isolation_status.bat`, `.\run_H_isolation_pause.bat`, `.\run_H_isolation_success.bat`, `python scripts\flows\A\A015_build_system_health_check.py --profile h --no-toast`, `.\run_H_isolation_resume.bat`.
- Success condition: controlled H run reaches terminal success/finalized state without a `phase1_pilot` max-runtime failure, H-scoped health is read only after finalization, and scheduler ownership is restored.
- If the condition fails: inspect the new H manifest and `phase1_pilot_wait_abnormal.*.json`; classify whether the remaining cause is stall, data, or workload budget before another code change.

## Live Evidence Update - 2026-05-11T09:26Z
- Newer live terminal after the code patch is still failed: `out/systems/H/live/H_cycle_last_terminal_info.txt` reports run `20260511T085704Z`, `state=failed`, `stage=phase1_pilot`, `failure_code=LOOP_RC_1`.
- Manifest evidence: `out/manifests/H/2026-05-11/H_20260511T085704Z.json` reports `phase1 pilot step timeout reason=max_runtime elapsed_seconds=903.45 stalled_seconds=15.11 stall_timeout_seconds=300 max_timeout_seconds=900`.
- This is not proof that the patch failed. It is live-owner proof still pending: the active scheduler owner was not paused/reloaded under the elevated isolation path, and active H ownership remains with pid `6364`.
- Current active H run at this update: `out/H_pricing_cycle.lock` shows `run_id=20260511T091540Z`, `start=2026-05-11T09:19:47Z`, `heartbeat=2026-05-11T09:26:03Z`.
- Status language: code fix applied; isolated tests passed; live loop verification not yet proven.
- Next verifier remains unchanged: elevated/admin H isolation window, then controlled H one-shot, H-scoped health after finalization, scheduler resume proof.

## Admin Pause Attempt - 2026-05-11T09:45Z
- User confirmed admin permission in chat.
- Status check still reported `is_admin=false`; task `AMZ H Cycle` remained enabled/ready and active H lock was `run_id=20260511T093630Z`.
- Attempted command: `.\run_H_isolation_pause.bat`.
- Result: blocked before any scheduler change with `pause requires elevation. Re-run from elevated PowerShell or cmd (Run as administrator).`
- No controlled H one-shot was started because scheduler ownership could not be paused safely from this shell.
- Next verifier is still the exact elevated/admin sequence above, starting with `.\run_H_isolation_pause.bat` from an elevated shell.

## Elevated Isolation Proof - 2026-05-11T10:45Z
- User ran `.\run_H_isolation_pause.bat` from an elevated shell. Result: scheduler task `AMZ H Cycle` disabled, controlled mode active, owner process count 0, H launcher/cycle locks reconciled and removed.
- First controlled proof run `20260511T095730Z` failed before phase1 pilot at `stage=item_offers`, `failure_code=LOOP_RC_2`.
- Root cause for that blocker: item-offers helper subprocess returned `rc=0` but did not create the expected JSON output contract file after the visibility wait.
- Code fix applied in `scripts/cycles/run_H_pricing_cycle.py`: after a subprocess `rc=0` missing-output condition and configured retry path, H now runs the same item-offers lookup inline and writes the expected boundary payload. If inline recovery is disabled or still cannot create output, the existing fail-closed error remains.
- Focused tests passed after patch: `python -m pytest tests\test_h_worker_lifecycle_contract.py tests\test_h110_market_payload_snapshot_floor.py -q` -> `51 passed`.
- Controlled proof rerun passed: `.\run_H_isolation_success.bat` -> `success=true`, terminal `run_id=20260511T101337Z`, `run_state=finalized`, `run_publish_status=ok`, `worker_state=succeeded`, `expected_outputs_ok=1`.
- H-scoped health after finalization initially showed `h_strategy_outcome_daily_count_integrity=fail 1`. Root cause was a derived daily-rollup mismatch against the source H outcome log: the `2026-05-10|share_hold|SELLER_DETAIL_HOLD` rollup had 1292 decisions while the source log had 1293 rows.
- Recovery run: `python scripts\one_off\H162_rebuild_strategy_outcome_daily.py` rebuilt local H strategy daily output from the source log and normalized historical non-action hold rows. Follow-up dry-run returned zero remaining conversions.
- H-scoped health after recovery: `python scripts\flows\A\A015_build_system_health_check.py --profile h --no-toast` -> `fail_count=0`, `warn_count=4`, `h_strategy_outcome_daily_count_integrity=ok 0`. Command exit code was 1 only because the H profile exits on WARN.
- Due check register updated: `H_STAGED_PUBLISH_RETRY_PATCH_LIVE_PROOF` marked completed/pass using controlled H proof run `20260511T101337Z` and `phase1_staged_publish_status=ok`.
- Ownership restoration is still pending because this shell is not elevated. Attempted `.\run_H_isolation_resume.bat` returned `resume requires elevation`.
- Exact next action: run `.\run_H_isolation_resume.bat` from elevated PowerShell, then confirm `.\run_H_isolation_status.bat` shows controlled mode false and scheduler ownership restored.

## Scheduler Ownership Restored - 2026-05-11T10:56Z
- User ran `.\run_H_isolation_resume.bat` from elevated PowerShell at `2026-05-11T10:55Z`.
- Resume result: `success=true`; controlled mode flag cleared; scheduled task `AMZ H Cycle` enabled and `Ready`; scheduler run attempted successfully.
- Local confirmation: `.\run_H_isolation_status.bat` at `2026-05-11T10:55:49Z` showed task `Enabled/Ready`, `controlled_mode_active=false`, live launcher lock present, live H cycle lock present, and runtime status `RUNNING` at `stage=child_wait`.
- PID confirmation: launcher `29256`, wrapper `14252`, and child `16908` all exist.
- Final runtime status: code fix applied; isolated verification passed; controlled H proof passed; H-scoped health has `fail_count=0`; scheduler ownership restored.
- Remaining H health WARNs are monitoring items, not blockers for this proof: strategy sample-size WARNs and referral-source coverage WARN.

## Reopened Timeout-Progressing Evidence - 2026-05-18T12:05:16Z
- Read-only autopsy found the latest H manifest `out/manifests/H/2026-05-18/H_20260518T110904Z.json` failed in the same class: `TIMEOUT_PROGRESSING`.
- Evidence detail: `phase1 pilot step timeout reason=max_runtime`, `elapsed_seconds=1804.97`, `stalled_seconds=61.11`, `effective_max_timeout_seconds=1800`, and a fresh progress tail at `2026-05-18T11:39:41Z`.
- Root cause remains workload budget, not a true stall.
- Code hardening applied in `scripts/cycles/run_H_pricing_cycle.py`:
  - default `H_PHASE1_PILOT_MAX_PROGRESS_GRACE_SECONDS` increased from `900` to `2700`.
  - true stall timeout still wins when `stalled_seconds` reaches the stall threshold.
- Isolated verification passed:
  - `python -m py_compile scripts/cycles/run_H_pricing_cycle.py`
  - `python -m pytest tests/test_h_worker_lifecycle_contract.py -q` -> 52 passed
- Live loop verification is not yet proven because the failed live run started before this change was loaded.
- Durable follow-up: `project_control/DUE_CHECK_REGISTER.csv` row `H_TIMEOUT_PROGRESSING_20260518_FRESH_OWNER_PROOF`.

Required next verifier:
- Exact trigger: next fresh H owner process started after `2026-05-18T12:05:16Z`, preferably through the H-owned controlled proof path.
- Artifact: latest `out/manifests/H/YYYY-MM-DD/H_*.json` plus `out/systems/H/live/H_cycle_last_terminal_info.txt`.
- Success condition: H reaches terminal success/finalized without a `phase1_pilot` max-runtime failure, or any remaining timeout evidence shows a different root cause.
- If the condition fails: if it still dies as `TIMEOUT_PROGRESSING` at the larger bounded budget, move to chunk/checkpoint/resume instead of raising the budget again.
