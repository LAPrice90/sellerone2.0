# Controlled Restart Recovery - 2026-05-06

## Current Phase
Isolated verification passed; live restart proof pending.

The controller now preserves the terminal skip decision when post-heal owner relaunch creates fresh owner locks. Post-heal relaunch evidence is recorded, but it is no longer allowed to become the final reboot approval/skip gate when reboot execution was enabled and the pre-heal decision was `skipped`.

## Allowed Files
- `scripts/tools/controlled_restart_controller.py`
- `scripts/tools/controlled_restart_gate.py` only if gate classification needs a narrow supporting change
- `tests/test_phase2_control_layer_deconflict.py`
- `tests/test_controlled_restart_gate.py`
- `project_control/TASK_QUEUE.md`
- this plan file

## Evidence From MOT
- `AMZ Controlled Restart` ran at 2026-05-06 02:10:02 local with task result 0.
- OS boot time remained 2026-05-05 02:24:12, so no 2026-05-06 reboot occurred.
- `out/locks/restart_control/restart_controller.latest.json` ended `skipped_post_heal_blocked`.
- Final blockers were `H_LAUNCHER_ACTIVE`, `H_CYCLE_ACTIVE_LOCK`, `B_ACTIVE_LOCK`, `F_MANAGER_ACTIVE_LOCK`, and `AMBIGUOUS_OWNERSHIP_HOLD`.

## Tests And Isolated Proof
- Added focused tests for controller post-wait behavior.
- Passed: `pytest tests/test_phase2_control_layer_deconflict.py tests/test_controlled_restart_gate.py -q`.
- Passed: `python -m py_compile scripts/tools/controlled_restart_controller.py scripts/tools/controlled_restart_gate.py`.
- Do not submit an OS reboot during isolated proof.

## Live Proof Target
- Next verifier: next scheduled `AMZ Controlled Restart` window or an explicitly approved dry-run/controller simulation that cannot call `shutdown`.
- Success condition: the controller either reaches a clean drain-boundary approval path before owner relaunch, or records one explicit safe skip reason without relaunching owners into a self-blocking final gate.
- Failure action: keep this plan active, inspect `out/locks/restart_control/restart_controller.latest.json`, and patch the earliest controller/gate branch that contradicts the recorded owner state.

## Monitoring
- First check: next time `out/locks/restart_control/restart_controller.latest.json` changes after this fix.
- Artifact to inspect: `out/locks/restart_control/restart_controller.latest.json`.
- Success condition: `outcome` is not `skipped_post_heal_blocked` with freshly relaunched owner-lock blockers.
- Timeout rule: if no controlled restart run has occurred by the next morning MOT, classify as `parked pending next proof window`.

## Verification Status
- Code fix applied: yes.
- Isolated verification passed: yes.
- Live loop verification: not yet proven.
- Next verifier: next scheduled `AMZ Controlled Restart` run.
