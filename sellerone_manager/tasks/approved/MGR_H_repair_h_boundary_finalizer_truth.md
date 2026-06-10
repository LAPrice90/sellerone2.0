# H Repair Package - Repeated Boundary Finalizer Timeout - 2026-05-31

## Manager Authority
- task_id: MGR_H_repair_h_boundary_finalizer_truth
- job_ref: H-REPEATED-BOUNDARY-FINALIZER
- status: proved
- authority: standing_safe_code_repair
- luke_action_required: 0

## Boundary
- allowed_scope: - `scripts/cycles/run_H_pricing_cycle.py` - `scripts/phase1/phase1_main_loop.py` - H lifecycle/finalizer helper code directly called by those files - focused H lifecycle/finalizer tests under `tests/` - manager H MOT tests under `tests/manager/` - this repair package and `CODING_PLAN.md`
- forbidden_actions: - Do not run H from Codex. - Do not pause or resume scheduler ownership. - Do not publish. - Do not change prices. - Do not edit queues. - Do not write Google Sheets. - Do not align local DB facts. - Do not delete outputs. - Do not restart workers. - Do not hand-edit manifests, terminal markers, MOT rows, or health outputs. - Do not widen into A, B, E, F, or O.
- proof_required: - First isolate the finalizer timeout path in code and tests. - Prove the finalizer can treat completed `50/50` scan-state progress as a safe terminal boundary when the child has already finished useful work. - Compile touched H files. - Run focused H lifecycle/finalizer tests. - Run manager H MOT tests. - A real proof is only complete after an H-owned run leaves: - latest manifest final state `completed` - terminal state `finalized` - publish status `ok` or a clearly safe parked state - `h_boundary_finalizer_truth=ok` in independent H MOT
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow H
- rollback_path: - Use git diff for code rollback. - Do not edit H output files to make the MOT pass. - If a future code repair changes finalizer behavior, revert only the touched H finalizer/lifecycle code and rerun focused tests plus H MOT.
- stop_condition: - Stop if the root cause is not the boundary/finalizer timeout after scan-state progress. - Stop if proof requires a protected action: H run, scheduler pause/resume, publish, price change, queue edit, Sheet write, DB alignment, output deletion, worker restart, or scope widening. - Stop if a newer natural H run proves the boundary clean; record that as proof but keep this package as intermittent-failure evidence until repeated failures stop.

## Source
- source_type: repair_package
- source_id: H_REPAIR_PACKAGE_MOT_H_H_BOUNDARY_FINALIZER_TRUTH_20260531_REPEATED_TIMEOUT
- source_path: plans\active\sellerone-manager-control-plane-v1\H_REPAIR_PACKAGE_MOT_H_H_BOUNDARY_FINALIZER_TRUTH_20260531_REPEATED_TIMEOUT.md

## Exact Source Row
```json
{
  "source_id": "H_REPAIR_PACKAGE_MOT_H_H_BOUNDARY_FINALIZER_TRUTH_20260531_REPEATED_TIMEOUT",
  "source_path": "plans\\active\\sellerone-manager-control-plane-v1\\H_REPAIR_PACKAGE_MOT_H_H_BOUNDARY_FINALIZER_TRUTH_20260531_REPEATED_TIMEOUT.md"
}
```
