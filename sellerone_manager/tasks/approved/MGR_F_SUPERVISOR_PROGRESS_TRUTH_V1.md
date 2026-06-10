# F Supervisor Progress Truth v1

## Manager Authority
- task_id: MGR_F_SUPERVISOR_PROGRESS_TRUTH_V1
- job_ref: F-SUPERVISOR-PROGRESS
- flow: F
- task_type: bounded_f_manager_repair
- priority: high
- status: proved
- authority: manager_visible_f_status_truth
- luke_action_required: 0

## Boundary
- allowed_scope: F supervisor and manager-visible progress wording only. Make the F status distinguish process heartbeat from real scanner row/output progress.
- forbidden_actions: Do not run F061. Do not restart workers. Do not edit the F061 queue or active_run files. Do not approve handoff. Do not fetch Gmail, download supplier files, write Google Sheets, change prices, align local DB facts, delete outputs, or open a browser.
- proof_required: F supervisor/status must not say or imply working solely because heartbeat files are fresh. It must show process alive separately from last scanner chunk, last child output, active supplier, pending rows, and no-progress warning age.
- retest_command: python -m pytest tests/manager/test_hourly_mot.py tests/test_fpm130_live_cycle.py -k "f_ or supervisor or progress" -q
- rollback_path: Use git diff for code rollback. Do not alter live scanner outputs to make status look better.
- stop_condition: Stop when F status/proof truth is code-tested and manager-visible, or stop immediately if the fix requires live scanner action, queue edits, worker restart, output deletion, Sheets, prices, local DB alignment, or scope widening.

## Current Evidence
- F supervisor state can report fresh status using `freshest_live_state_seconds`.
- The child status heartbeat can be fresh while the latest scanner chunk event is older.
- This makes the UI/operator label look like "working 0 minutes ago" even when the scanner may only be alive, not progressing.

## Intended Rule
The F status should say:
- process alive, when only heartbeat/process proof is fresh
- scanner progressing, only when scanner chunk/output progress is fresh
- no row progress, when heartbeat is fresh but scanner chunks/output are stale
- blocked/waiting, when login, source, or protected decision proof explains the pause

## Worker Instructions
1. Inspect the F supervisor/status producer and the UI/manager readers.
2. Add progress-age proof based on scanner chunk or equivalent real output movement.
3. Keep heartbeat/process proof separate from row-progress proof.
4. Update tests so a fresh heartbeat without recent scanner progress cannot produce a misleading working label.
5. Retest with offline/unit tests and read-only manager outputs only.
