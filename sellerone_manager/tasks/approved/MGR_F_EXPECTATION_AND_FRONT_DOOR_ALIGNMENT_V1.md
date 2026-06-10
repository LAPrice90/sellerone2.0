# F expectation and front-door alignment

- task_id: MGR_F_EXPECTATION_AND_FRONT_DOOR_ALIGNMENT_V1
- job_ref: F-EXPECTATION-AND-FRONT
- flow: F
- status: proved
- authority: manager_task_packaging_only
- luke_action_required: 0
- priority: normal
- task_type: manager_visibility_gap
- retest_command: python -m sellerone_manager.app --hourly-mot --mot-flow F
- rollback_path: Use git diff for code rollback. Do not alter live F queue, scanner, source, or business outputs to satisfy proof.
- stop_condition: Stop if the work crosses into F061 runtime, queue state, supplier fetching, Sheets, prices, local DB alignment, output deletion, or worker ownership.

## Allowed Work
- Create or update the formal F expectation file under `project_control/EXPECTATIONS/`.
- Keep the F blueprint and formal expectation file aligned in plain English.
- Make the main manager front door reflect the independent F MOT truth without hiding active F task-board rows.
- Add or update manager-only tests for expectation coverage and front-door summary alignment.

## Forbidden Work
- Do not run F061.
- Do not run live scanner proof.
- Do not edit the F061 queue.
- Do not fetch Gmail, download attachments, delete Gmail, or download supplier URLs.
- Do not change prices.
- Do not write Google Sheets.
- Do not change local DB facts.
- Do not delete outputs.
- Do not restart workers.
- Do not open a separate Chrome login window.

## Acceptance Proof
- A formal F expectation file exists under `project_control/EXPECTATIONS/`, or the manager records a clear explicit exemption.
- `python -m sellerone_manager.app --hourly-mot --mot-flow F` still runs read-only.
- `python -m sellerone_manager.app --what-next` does not call F calm while active F independent MOT failures remain.
- The Manager Task Board continues to show the active F work from MOT packets.
