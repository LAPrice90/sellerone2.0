# H Repair Package - Repeated Boundary Finalizer Timeout - 2026-05-31

## Root Cause Summary
- The active H failure is `h_boundary_finalizer_truth`.
- This is not a price-write or publish-success proof.
- H is completing useful phase 1 pilot work, reaching `50/50` SKU progress, and writing scan-state progress.
- The failure happens after that progress, around the boundary/finalizer window.
- Two recent failed runs show the same pattern:
  - `H_20260531T072631Z`
  - `H_20260531T075811Z`
- Both failed with `TIMEOUT_STALLED`.
- Both show `throughput_recovery_scan_state_advanced_count ... advanced_count=50 status=ok`.
- Both ended with terminal state `failed` and publish status `not_started`.
- A newer H owner started by itself after the failure, so Codex must not restart or interfere with H.

## Current Failed Checks Grouped Into One Issue
- `h_latest_manifest_state`
- `h_terminal_publish_truth`
- `h_boundary_finalizer_truth`
- `h_manager_readiness`

These are one issue, not four separate repairs: H has a repeated finalizer/boundary timeout after completing phase 1 pilot progress.

## Allowed Files For A Future Repair Batch
- `scripts/cycles/run_H_pricing_cycle.py`
- `scripts/phase1/phase1_main_loop.py`
- H lifecycle/finalizer helper code directly called by those files
- focused H lifecycle/finalizer tests under `tests/`
- manager H MOT tests under `tests/manager/`
- this repair package and `CODING_PLAN.md`

## Forbidden Files And Actions
- Do not run H from Codex.
- Do not pause or resume scheduler ownership.
- Do not publish.
- Do not change prices.
- Do not edit queues.
- Do not write Google Sheets.
- Do not align local DB facts.
- Do not delete outputs.
- Do not restart workers.
- Do not hand-edit manifests, terminal markers, MOT rows, or health outputs.
- Do not widen into A, B, E, F, or O.

## Proof Path For A Future Repair
- First isolate the finalizer timeout path in code and tests.
- Prove the finalizer can treat completed `50/50` scan-state progress as a safe terminal boundary when the child has already finished useful work.
- Compile touched H files.
- Run focused H lifecycle/finalizer tests.
- Run manager H MOT tests.
- A real proof is only complete after an H-owned run leaves:
  - latest manifest final state `completed`
  - terminal state `finalized`
  - publish status `ok` or a clearly safe parked state
  - `h_boundary_finalizer_truth=ok` in independent H MOT

## Retest Command
python -m sellerone_manager.app --hourly-mot --mot-flow H

## Rollback Path
- Use git diff for code rollback.
- Do not edit H output files to make the MOT pass.
- If a future code repair changes finalizer behavior, revert only the touched H finalizer/lifecycle code and rerun focused tests plus H MOT.

## Stop Condition
- Stop if the root cause is not the boundary/finalizer timeout after scan-state progress.
- Stop if proof requires a protected action: H run, scheduler pause/resume, publish, price change, queue edit, Sheet write, DB alignment, output deletion, worker restart, or scope widening.
- Stop if a newer natural H run proves the boundary clean; record that as proof but keep this package as intermittent-failure evidence until repeated failures stop.
